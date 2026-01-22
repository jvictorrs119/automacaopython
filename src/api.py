from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from typing import List
import uuid
from datetime import datetime, date
import random
import string

from src.models import OrderCreate, PartsListCreate, OrdemPedido, Peca, AlertaAtraso, CatalogoItemCreate, TipoItemCatalogo, EstoqueItemCreate, EstoqueItemUpdate
from src.database import get_supabase
import os
import requests
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import tools for the agent logic
from src.tools import (
    extract_data_from_message,
    extract_parts_from_message,
    generate_agent_response,
    get_chat_response
)
from src.templates import (
    format_order_confirmation,
    format_order_created_success,
    format_parts_confirmation,
    format_update_confirmation,
    format_update_success,
    format_delete_confirmation,
    format_delete_success,
    format_search_results
)
from src.help_commands import get_menu_help, get_command_help, is_help_command


import json

app = FastAPI(title="Production Monitoring API")

class ChatRequest(BaseModel):
    message: str
    phone_number: Optional[str] = None # Identifier for the session
    history: List[dict] = [] 
    context: Optional[Dict[str, Any]] = None 

class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    new_context: Optional[Dict[str, Any]] = None
    tokens_used: int = 0  # Total tokens used in this interaction

def trigger_n8n_webhook(data: dict):
    """Send data to n8n webhook if URL is configured"""
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if webhook_url:
        try:
            requests.post(webhook_url, json=data, timeout=5)
        except Exception as e:
            print(f"Failed to trigger n8n: {e}")

@app.get("/")
def read_root():
    return {"message": "Production Monitoring API is running"}

@app.post("/orders", response_model=dict)
def create_order(order: OrderCreate):
    supabase = get_supabase()
    
    # Generate a unique OP code (6 chars, uppercase + digits)
    codigo_op = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Convert Pydantic model to dict with JSON-compatible types (dates to strings)
    order_data = jsonable_encoder(order)
    order_data["codigo_op"] = codigo_op
    order_data["status"] = "Em Produção"
    # data_entrega permanece null até a entrega ser realizada
    if not order_data.get("data_entrega"):
        order_data["data_entrega"] = None
    if not order_data.get("data_pedido"):
        order_data["data_pedido"] = date.today().isoformat()
    
    # Insert into Supabase
    try:
        response = supabase.table("ordem_pedido").insert(order_data).execute()
        # Check if response has data (supabase-py v2 returns an object with .data)
        if not response.data:
             raise HTTPException(status_code=500, detail="Failed to create order")
        
        # Trigger n8n automation
        trigger_n8n_webhook({
            "event": "new_order",
            "codigo_op": codigo_op,
            "data": order_data
        })
        
        return {"codigo_op": codigo_op, "message": "Order created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parts")
def create_parts(parts_list: PartsListCreate):
    supabase = get_supabase()
    
    # Fetch order details to get client name and delivery date (simplified)
    try:
        order_res = supabase.table("ordem_pedido").select("*").eq("codigo_op", parts_list.codigo_op).execute()
        if not order_res.data:
             raise HTTPException(status_code=404, detail="Order not found")
        
        order_info = order_res.data[0]
        
        parts_data = []
        for p in parts_list.pecas:
            part_dict = p.dict()
            part_dict["codigo_op"] = parts_list.codigo_op
            part_dict["status"] = "Pendente"
            part_dict["nome_cliente"] = order_info["nome_cliente"]
            part_dict["previsao_entrega"] = order_info["previsao_entrega"]
            part_dict["data_entrega"] = None  # Será preenchido quando a entrega for realizada
            part_dict["pecas_produzidas"] = 0 # Initial state
            parts_data.append(part_dict)
            
        response = supabase.table("pecas").insert(parts_data).execute()
        return {"message": f"Created {len(parts_data)} parts for {parts_list.codigo_op}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
def analyze_production():
    supabase = get_supabase()
    alerts_created = []
    
    try:
        # Fetch active orders/parts
        # For this demo, we'll check 'pecas' table as it has the granular status
        parts_res = supabase.table("pecas").select("*").neq("status", "Concluido").execute()
        parts = parts_res.data
        
        today = date.today()
        
        for part in parts:
            alert_reason = None
            
            # Parse dates - usar previsao_entrega para cálculo de atraso
            previsao_entrega = datetime.strptime(part["previsao_entrega"], "%Y-%m-%d").date()
            
            # Logic 1: Delay (Today > Previsao Entrega)
            if today > previsao_entrega:
                alert_reason = f"Atraso na entrega (Era para {previsao_entrega})"
            
            # Logic 2: Production Deviation (< 70% goal AND > 50% time elapsed)
            # We need 'data_pedido' or start date to calculate time elapsed. 
            # For simplicity, let's assume we fetch the order to get 'data_pedido'
            # Optimization: In a real app, join tables. Here, we do a separate query or assume data available.
            # Let's skip complex time calc for this MVP and focus on the explicit rule provided:
            # "produção < 70% da meta" -> pecas_produzidas < 0.7 * quantidade
            
            if not alert_reason:
                target = part["quantidade"]
                produced = part["pecas_produzidas"]
                if produced < (0.7 * target):
                    # Check time elapsed? We need order date.
                    # Let's fetch order date for this part's OP
                    order_res = supabase.table("ordem_pedido").select("data_pedido, previsao_entrega").eq("codigo_op", part["codigo_op"]).execute()
                    if order_res.data:
                        o = order_res.data[0]
                        d_pedido = datetime.strptime(o["data_pedido"], "%Y-%m-%d").date()
                        d_previsao = datetime.strptime(o["previsao_entrega"], "%Y-%m-%d").date()
                        
                        total_days = (d_previsao - d_pedido).days
                        if total_days > 0:
                            elapsed = (today - d_pedido).days
                            if (elapsed / total_days) > 0.5:
                                alert_reason = "Baixa produção (<70%) com >50% do prazo decorrido"

            if alert_reason:
                # Check if alert already exists to avoid duplicates (optional but good)
                # For MVP, just insert.
                
                alert_data = {
                    "nome_cliente": part["nome_cliente"],
                    "previsao_entrega": part["previsao_entrega"],
                    "codigo_op": part["codigo_op"],
                    "nome_peca": part["nome_peca"],
                    "criado_em": datetime.now().isoformat()
                }
                
                # Insert alert
                supabase.table("alerta_atraso").insert(alert_data).execute()
                
                alerts_created.append({
                    "codigo_op": part["codigo_op"],
                    "peca": part["nome_peca"],
                    "motivo": alert_reason
                })
                
        return {"alerts": alerts_created, "count": len(alerts_created)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CRUD for Orders ---

@app.get("/orders")
def search_orders(query: str = None):
    supabase = get_supabase()
    try:
        if query:
            # Search by client name, OP code, or status
            # Supabase 'or' syntax: column.operator.value,column.operator.value
            response = supabase.table("ordem_pedido").select("*").or_(f"nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
        else:
            # Return all (limit to 50 for safety)
            response = supabase.table("ordem_pedido").select("*").limit(50).execute()
            
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/{codigo_op}")
def get_order(codigo_op: str):
    supabase = get_supabase()
    try:
        response = supabase.table("ordem_pedido").select("*").eq("codigo_op", codigo_op).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Order not found")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/orders/{codigo_op}")
def update_order(codigo_op: str, order_update: dict):
    supabase = get_supabase()
    try:
        # Prevent updating critical fields if needed, for now allow all
        response = supabase.table("ordem_pedido").update(order_update).eq("codigo_op", codigo_op).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Order not found or not updated")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/orders/{codigo_op}")
def delete_order(codigo_op: str):
    supabase = get_supabase()
    try:
        # First, get all parts for this order to delete their history
        parts_res = supabase.table("pecas").select("id_peca").eq("codigo_op", codigo_op).execute()
        if parts_res.data:
            part_ids = [p["id_peca"] for p in parts_res.data]
            # Delete history for all parts of this order
            supabase.table("historico_status").delete().in_("id_peca", part_ids).execute()
        
        # Delete alerts related to this order
        supabase.table("alerta_atraso").delete().eq("codigo_op", codigo_op).execute()
        
        # Delete parts associated with this order
        supabase.table("pecas").delete().eq("codigo_op", codigo_op).execute()
        
        # Then delete the order
        response = supabase.table("ordem_pedido").delete().eq("codigo_op", codigo_op).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"message": f"Order {codigo_op} and its parts deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/{codigo_op}/parts")
def get_order_parts(codigo_op: str):
    supabase = get_supabase()
    try:
        response = supabase.table("pecas").select("*").eq("codigo_op", codigo_op).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CRUD for Parts ---

@app.get("/parts/search")
def search_parts(query: str = None):
    supabase = get_supabase()
    try:
        if query:
            # Search by part name, client name, OP code, or status
            response = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{query}%,nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
        else:
            response = supabase.table("pecas").select("*").limit(50).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/parts/{part_id}")
def update_part(part_id: str, part_update: dict):
    supabase = get_supabase()
    try:
        response = supabase.table("pecas").update(part_update).eq("id_peca", part_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Part not found")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/parts/{part_id}")
def delete_part(part_id: str):
    supabase = get_supabase()
    try:
        # First delete history for this part
        supabase.table("historico_status").delete().eq("id_peca", part_id).execute()
        
        # Then delete the part
        response = supabase.table("pecas").delete().eq("id_peca", part_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Part not found")
        return {"message": "Part deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Agent Chat Endpoint ---

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Intelligent endpoint that processes user messages.
    Manages context in a single Supabase table 'chat_sessions'.
    """
    try:
        supabase = get_supabase()
        message = req.message
        phone = req.phone_number
        
        # 0. Check for help commands (commands starting with /)
        if is_help_command(message):
            command = message.strip().lower()
            
            if command == "/menu":
                return ChatResponse(response=get_menu_help(), tokens_used=0)
            else:
                help_text = get_command_help(command)
                if help_text:
                    return ChatResponse(response=help_text, tokens_used=0)
                else:
                    return ChatResponse(
                        response="❌ Comando não reconhecido.\n\nDigite `/menu` para ver todos os comandos disponíveis.",
                        tokens_used=0
                    )
        
        # 1. Load Context and History from Supabase
        history_objs = [] # List of dicts: [{"role": "...", "content": "..."}]
        history_str_list = [] # List of strings for the agent tool: ["ROLE: Content"]
        state = {}
        
        if phone:
            try:
                # Fetch session
                res = supabase.table("chat_sessions").select("*").eq("phone_number", phone).execute()
                if res.data:
                    session = res.data[0]
                    history_objs = session.get("history") or []
                    state = session.get("state") or {}
                    
                    # Prepare history for the tool (Last 5 messages)
                    # history_objs is stored chronologically (oldest first)
                    # We take the last 5
                    if isinstance(history_objs, list):
                        recent_history = history_objs[-5:]
                        history_str_list = [f"{h.get('role', 'UNKNOWN').upper()}: {h.get('content', '')}" for h in recent_history if isinstance(h, dict)]
                    else:
                        history_objs = []
                    
            except Exception as e:
                print(f"Failed to load session from Supabase: {e}")

        # Append current user message for the tool logic
        user_msg_str = f"USER: {message}"
        history_str_list.append(user_msg_str)
        
        # 2. Analyze Message
        current_data = state.get("partial_data")
        
        # Token accumulator for this interaction
        total_tokens_used = 0
        
        # Extract data using the history
        extraction, extraction_tokens = extract_data_from_message(message, current_data, history_str_list)
        total_tokens_used += extraction_tokens
        
        response_obj = None
        
        if not extraction:
            response_obj = ChatResponse(response="Desculpe, tive um erro interno.", tokens_used=total_tokens_used)
        else:
            # --- PARTS CONFIRMATION (after order creation) ---
            if state.get("awaiting_parts_confirmation") and state.get("pending_parts"):
                is_yes = any(k in message.lower() for k in ["sim", "s", "yes", "ok", "confirm", "pode", "confirmo"])
                is_no = any(k in message.lower() for k in ["não", "nao", "no", "cancel", "cancelar"])
                
                if is_yes:
                    # Register the pending parts
                    active_op = state.get("active_order_op")
                    pending_parts = state.get("pending_parts", [])
                    
                    if active_op and pending_parts:
                        # Fetch order info for client name and delivery date
                        order_res = supabase.table("ordem_pedido").select("*").eq("codigo_op", active_op).execute()
                        if order_res.data:
                            order_info = order_res.data[0]
                            parts_payload = []
                            for p in pending_parts:
                                part_dict = {
                                    "nome_peca": p.get("nome_peca"),
                                    "quantidade": p.get("quantidade"),
                                    "preco_unitario": p.get("preco_unitario", 0),
                                    "codigo_op": active_op,
                                    "status": "Pendente",
                                    "nome_cliente": order_info["nome_cliente"],
                                    "previsao_entrega": order_info["previsao_entrega"],
                                    "data_entrega": None,  # Será preenchido quando a entrega for realizada
                                    "pecas_produzidas": 0
                                }
                                parts_payload.append(part_dict)
                            
                            supabase.table("pecas").insert(parts_payload).execute()
                            
                            msg = f"✅ *Peças cadastradas com sucesso!*\n\n"
                            msg += f"📦 {len(parts_payload)} peça(s) adicionada(s) à OP `{active_op}`\n\n"
                            msg += "O sistema agora está monitorando esta produção."
                            
                            response_obj = ChatResponse(
                                response=msg, 
                                new_context={
                                    "active_order_op": active_op,
                                    "awaiting_parts_confirmation": False,
                                    "pending_parts": []
                                },
                                tokens_used=total_tokens_used
                            )
                        else:
                            response_obj = ChatResponse(
                                response=f"❌ Erro: Pedido {active_op} não encontrado.", 
                                new_context={"awaiting_parts_confirmation": False, "pending_parts": []},
                                tokens_used=total_tokens_used
                            )
                    else:
                        response_obj = ChatResponse(
                            response="❌ Erro: Dados de peças ou OP perdidos.", 
                            new_context={"awaiting_parts_confirmation": False, "pending_parts": []},
                            tokens_used=total_tokens_used
                        )
                
                elif is_no:
                    msg = "Ok, as peças não foram cadastradas. Você pode cadastrá-las mais tarde se desejar."
                    response_obj = ChatResponse(
                        response=msg, 
                        new_context={
                            "active_order_op": state.get("active_order_op"),
                            "awaiting_parts_confirmation": False,
                            "pending_parts": []
                        },
                        tokens_used=total_tokens_used
                    )
                else:
                    # Not a clear yes/no - remind user
                    msg = "Por favor, responda com *Sim* para cadastrar as peças ou *Não* para pular."
                    response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
            
            # --- CATALOG INTENT ---
            elif extraction.get("is_catalog_intent"):
                catalog_action = extraction.get("catalog_action", "create")
                catalog_data = extraction.get("catalog_data", {})
                catalog_missing = extraction.get("catalog_missing_fields", [])
                catalog_missing_msg = extraction.get("catalog_missing_message")
                
                if catalog_action == "create":
                    # Check if awaiting confirmation
                    if state.get("awaiting_catalog_confirmation"):
                        if any(k in message.lower() for k in ["sim", "s", "yes", "confirm", "ok"]):
                            # Create the catalog item
                            pending_item = state.get("pending_catalog_item", {})
                            try:
                                item_payload = {
                                    "nome": pending_item.get("nome"),
                                    "preco": pending_item.get("preco"),
                                    "tipo": pending_item.get("tipo"),
                                    "created_at": datetime.now().isoformat(),
                                    "updated_at": datetime.now().isoformat()
                                }
                                
                                # Add tempo_producao for Produto Final
                                if pending_item.get("tipo") == "Produto Final":
                                    item_payload["tempo_producao"] = pending_item.get("tempo_producao")
                                
                                result = supabase.table("catalogo_pecas").insert(item_payload).execute()
                                
                                if result.data:
                                    msg = f"✅ *Item cadastrado no catálogo com sucesso!*\n\n"
                                    msg += f"📦 *Nome:* {pending_item.get('nome')}\n"
                                    msg += f"💰 *Preço:* R$ {pending_item.get('preco'):.2f}\n"
                                    msg += f"🏷️ *Tipo:* {pending_item.get('tipo')}\n"
                                    if pending_item.get("tempo_producao"):
                                        msg += f"⏱️ *Tempo de Produção:* {pending_item.get('tempo_producao')} min\n"
                                    msg += f"\n🆔 *ID:* `{result.data[0]['id']}`"
                                    response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                                else:
                                    response_obj = ChatResponse(response="❌ Erro ao cadastrar item no catálogo.", tokens_used=total_tokens_used)
                            except Exception as e:
                                response_obj = ChatResponse(response=f"❌ Erro: {str(e)}", tokens_used=total_tokens_used)
                        else:
                            msg = "❌ Cadastro de item no catálogo cancelado."
                            response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                    
                    # Check for missing fields
                    elif catalog_missing and catalog_missing_msg:
                        response_obj = ChatResponse(
                            response=catalog_missing_msg, 
                            new_context={"partial_catalog_data": catalog_data},
                            tokens_used=total_tokens_used
                        )
                    
                    # All data present - ask for confirmation
                    elif catalog_data.get("nome") and catalog_data.get("preco") is not None and catalog_data.get("tipo"):
                        # Validate tipo
                        valid_types = ["Produto Final", "Itens Consumíveis", "Matérias Primas", "Inventário"]
                        tipo = catalog_data.get("tipo")
                        
                        # Normalize tipo
                        tipo_lower = tipo.lower()
                        if "consumiv" in tipo_lower or "consumív" in tipo_lower:
                            tipo = "Itens Consumíveis"
                        elif "materia" in tipo_lower or "matéria" in tipo_lower or "prima" in tipo_lower:
                            tipo = "Matérias Primas"
                        elif "produto" in tipo_lower or "final" in tipo_lower:
                            tipo = "Produto Final"
                        elif "inventar" in tipo_lower or "inventário" in tipo_lower:
                            tipo = "Inventário"
                        
                        catalog_data["tipo"] = tipo
                        
                        # Check tempo_producao for Produto Final
                        if tipo == "Produto Final" and not catalog_data.get("tempo_producao"):
                            msg = "⏱️ Para cadastrar um *Produto Final*, preciso saber o *tempo de produção* (em minutos). Qual é o tempo de produção deste item?"
                            response_obj = ChatResponse(
                                response=msg,
                                new_context={"partial_catalog_data": catalog_data},
                                tokens_used=total_tokens_used
                            )
                        else:
                            # Show confirmation
                            msg = "📦 *Confirmar cadastro no catálogo:*\n\n"
                            msg += f"• *Nome:* {catalog_data.get('nome')}\n"
                            msg += f"• *Preço:* R$ {float(catalog_data.get('preco')):.2f}\n"
                            msg += f"• *Tipo:* {tipo}\n"
                            if catalog_data.get("tempo_producao"):
                                msg += f"• *Tempo de Produção:* {catalog_data.get('tempo_producao')} min\n"
                            msg += "\n✅ Deseja confirmar o cadastro? (Sim/Não)"
                            
                            response_obj = ChatResponse(
                                response=msg,
                                new_context={
                                    "awaiting_catalog_confirmation": True,
                                    "pending_catalog_item": catalog_data
                                },
                                tokens_used=total_tokens_used
                            )
                    else:
                        # Missing required fields
                        missing = []
                        if not catalog_data.get("nome"):
                            missing.append("nome")
                        if catalog_data.get("preco") is None:
                            missing.append("preço")
                        if not catalog_data.get("tipo"):
                            missing.append("tipo (Produto Final, Itens Consumíveis, Matérias Primas ou Inventário)")
                        
                        msg = f"📝 Para cadastrar um item no catálogo, preciso das seguintes informações:\n\n"
                        for m in missing:
                            msg += f"• {m}\n"
                        msg += "\nPor favor, informe os dados completos."
                        
                        response_obj = ChatResponse(
                            response=msg,
                            new_context={"partial_catalog_data": catalog_data},
                            tokens_used=total_tokens_used
                        )
                
                elif catalog_action == "list":
                    # List catalog items
                    catalog_items = supabase.table("catalogo_pecas").select("*").order("created_at", desc=True).limit(20).execute()
                    if catalog_items.data:
                        msg = "📦 *Itens no Catálogo:*\n\n"
                        for item in catalog_items.data:
                            msg += f"• *{item['nome']}* - R$ {float(item['preco']):.2f} ({item['tipo']})\n"
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    else:
                        response_obj = ChatResponse(response="📦 O catálogo está vazio.", tokens_used=total_tokens_used)
            
            # --- STOCK INTENT ---
            elif extraction.get("is_stock_intent"):
                stock_action = extraction.get("stock_action", "add")
                stock_data = extraction.get("stock_data", {})
                stock_missing = extraction.get("stock_missing_fields", [])
                stock_missing_msg = extraction.get("stock_missing_message")
                
                if stock_action == "add":
                    # Check if awaiting confirmation
                    if state.get("awaiting_stock_confirmation"):
                        if any(k in message.lower() for k in ["sim", "s", "yes", "confirm", "ok"]):
                            # Add to stock
                            pending_stock = state.get("pending_stock_item", {})
                            catalog_item = pending_stock.get("catalog_item", {})
                            quantidade = pending_stock.get("quantidade", 0)
                            
                            try:
                                # Check if already exists in stock
                                stock_result = supabase.table("estoque").select("*").ilike("nome", catalog_item["nome"]).execute()
                                
                                if stock_result.data:
                                    # Update existing
                                    existing = stock_result.data[0]
                                    new_qty = existing["quantidade"] + quantidade
                                    
                                    supabase.table("estoque").update({
                                        "quantidade": new_qty,
                                        "updated_at": datetime.now().isoformat()
                                    }).eq("id", existing["id"]).execute()
                                    
                                    msg = f"✅ *Estoque atualizado!*\n\n"
                                    msg += f"📦 *{catalog_item['nome']}*\n"
                                    msg += f"• Quantidade anterior: {existing['quantidade']}\n"
                                    msg += f"• Adicionado: +{quantidade}\n"
                                    msg += f"• *Nova quantidade: {new_qty}*"
                                else:
                                    # Create new stock entry
                                    stock_payload = {
                                        "nome": catalog_item["nome"],
                                        "quantidade": quantidade,
                                        "preco_unitario": catalog_item["preco"],
                                        "tipo": catalog_item["tipo"],
                                        "created_at": datetime.now().isoformat(),
                                        "updated_at": datetime.now().isoformat()
                                    }
                                    
                                    result = supabase.table("estoque").insert(stock_payload).execute()
                                    
                                    msg = f"✅ *Item adicionado ao estoque!*\n\n"
                                    msg += f"📦 *{catalog_item['nome']}*\n"
                                    msg += f"• Quantidade: {quantidade}\n"
                                    msg += f"• Preço unitário: R$ {float(catalog_item['preco']):.2f}\n"
                                    msg += f"• Tipo: {catalog_item['tipo']}"
                                
                                response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                            except Exception as e:
                                response_obj = ChatResponse(response=f"❌ Erro ao adicionar ao estoque: {str(e)}", tokens_used=total_tokens_used)
                        else:
                            msg = "❌ Operação de estoque cancelada."
                            response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                    
                    # Check for missing fields
                    elif stock_missing and stock_missing_msg:
                        response_obj = ChatResponse(
                            response=stock_missing_msg,
                            new_context={"partial_stock_data": stock_data},
                            tokens_used=total_tokens_used
                        )
                    
                    # Check if we have name and quantity
                    elif stock_data.get("nome") and stock_data.get("quantidade"):
                        nome = stock_data.get("nome")
                        quantidade = stock_data.get("quantidade")
                        
                        # 1. Check if item exists in catalog
                        catalog_result = supabase.table("catalogo_pecas").select("*").ilike("nome", f"%{nome}%").execute()
                        
                        if not catalog_result.data:
                            msg = f"⚠️ O item *'{nome}'* não foi encontrado no catálogo.\n\n"
                            msg += "Para adicionar ao estoque, o item precisa estar cadastrado no catálogo primeiro.\n\n"
                            msg += "💡 Deseja cadastrar este item no catálogo agora?"
                            response_obj = ChatResponse(
                                response=msg,
                                new_context={"suggest_catalog_create": nome},
                                tokens_used=total_tokens_used
                            )
                        else:
                            catalog_item = catalog_result.data[0]
                            
                            # Check current stock
                            stock_check = supabase.table("estoque").select("*").ilike("nome", catalog_item["nome"]).execute()
                            current_qty = stock_check.data[0]["quantidade"] if stock_check.data else 0
                            
                            msg = f"📦 *Confirmar entrada no estoque:*\n\n"
                            msg += f"• *Item:* {catalog_item['nome']}\n"
                            msg += f"• *Tipo:* {catalog_item['tipo']}\n"
                            msg += f"• *Preço unitário:* R$ {float(catalog_item['preco']):.2f}\n"
                            msg += f"• *Quantidade atual:* {current_qty}\n"
                            msg += f"• *Quantidade a adicionar:* {quantidade}\n"
                            msg += f"• *Nova quantidade:* {current_qty + quantidade}\n"
                            msg += "\n✅ Confirmar? (Sim/Não)"
                            
                            response_obj = ChatResponse(
                                response=msg,
                                new_context={
                                    "awaiting_stock_confirmation": True,
                                    "pending_stock_item": {
                                        "catalog_item": catalog_item,
                                        "quantidade": quantidade
                                    }
                                },
                                tokens_used=total_tokens_used
                            )
                    else:
                        # Missing required fields
                        missing = []
                        if not stock_data.get("nome"):
                            missing.append("nome do item")
                        if not stock_data.get("quantidade"):
                            missing.append("quantidade")
                        
                        msg = f"📦 Para adicionar ao estoque, preciso das seguintes informações:\n\n"
                        for m in missing:
                            msg += f"• {m}\n"
                        msg += "\nPor favor, informe os dados."
                        
                        response_obj = ChatResponse(
                            response=msg,
                            new_context={"partial_stock_data": stock_data},
                            tokens_used=total_tokens_used
                        )
                
                elif stock_action == "list":
                    # List stock items
                    stock_items = supabase.table("estoque").select("*").order("nome").execute()
                    if stock_items.data:
                        msg = "📦 *Itens no Estoque:*\n\n"
                        total_value = 0
                        for item in stock_items.data:
                            value = float(item['preco_unitario']) * item['quantidade']
                            total_value += value
                            msg += f"• *{item['nome']}*: {item['quantidade']} un. (R$ {float(item['preco_unitario']):.2f}/un)\n"
                        msg += f"\n💰 *Valor total em estoque:* R$ {total_value:.2f}"
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    else:
                        response_obj = ChatResponse(response="📦 O estoque está vazio.", tokens_used=total_tokens_used)
                
                elif stock_action == "check":
                    nome = stock_data.get("nome", "")
                    if nome:
                        # Check in catalog
                        catalog_result = supabase.table("catalogo_pecas").select("*").ilike("nome", f"%{nome}%").execute()
                        # Check in stock
                        stock_result = supabase.table("estoque").select("*").ilike("nome", f"%{nome}%").execute()
                        
                        msg = f"🔍 *Verificação para '{nome}':*\n\n"
                        
                        if catalog_result.data:
                            item = catalog_result.data[0]
                            msg += f"✅ *Encontrado no catálogo:*\n"
                            msg += f"   • Nome: {item['nome']}\n"
                            msg += f"   • Preço: R$ {float(item['preco']):.2f}\n"
                            msg += f"   • Tipo: {item['tipo']}\n\n"
                        else:
                            msg += f"❌ *Não encontrado no catálogo*\n\n"
                        
                        if stock_result.data:
                            item = stock_result.data[0]
                            msg += f"✅ *Encontrado no estoque:*\n"
                            msg += f"   • Quantidade: {item['quantidade']} un.\n"
                            msg += f"   • Valor total: R$ {float(item['preco_unitario']) * item['quantidade']:.2f}"
                        else:
                            msg += f"❌ *Não encontrado no estoque*"
                        
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    else:
                        response_obj = ChatResponse(response="Qual item você deseja verificar?", tokens_used=total_tokens_used)
            
            # --- SEARCH INTENT ---
            elif extraction.get("is_search_intent"):
                query = extraction.get("search_query")
                if not query:
                    response_obj = ChatResponse(response="O que você deseja buscar?")
                else:
                    safe_query = query.strip()
                    orders_res = supabase.table("ordem_pedido").select("*").or_(f"nome_cliente.ilike.%{safe_query}%,codigo_op.ilike.%{safe_query}%,status.ilike.%{safe_query}%").execute()
                    parts_res = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{safe_query}%,nome_cliente.ilike.%{safe_query}%,codigo_op.ilike.%{safe_query}%,status.ilike.%{safe_query}%").execute()
                    
                    orders = orders_res.data
                    parts = parts_res.data
                    
                    if not orders and not parts:
                        msg, gen_tokens = generate_agent_response(message, {"status": "not_found", "query": query})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    else:
                        action_result = {"status": "success", "type": "search_results", "query": query, "orders": orders, "parts": parts}
                        msg = format_search_results(query, orders, parts)
                        
                        new_ctx = {}
                        # Save all results for context refinement
                        new_ctx["last_search_results"] = {"orders": orders, "parts": parts}
                        
                        # If single result, save as active item for future context
                        if len(orders) == 1 and not parts:
                            new_ctx["last_active_item"] = {"type": "order", "data": orders[0]}
                        elif len(parts) == 1 and not orders:
                            new_ctx["last_active_item"] = {"type": "part", "data": parts[0]}
                            
                        response_obj = ChatResponse(response=msg, action="search_result", data={"orders": orders, "parts": parts}, new_context=new_ctx, tokens_used=total_tokens_used)

            # --- DELETE INTENT ---
            elif extraction.get("is_delete_intent"):
                target = extraction.get("delete_target")
                query = extraction.get("delete_query")
                
                if state.get("awaiting_delete_confirmation"):
                    if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                        candidates = state.get("delete_candidates", [])
                        # Also support legacy single candidate
                        if not candidates and state.get("delete_candidate"):
                            candidates = [state.get("delete_candidate")]
                        
                        deleted_items = []
                        for candidate in candidates:
                            if candidate["type"] == "order":
                                # First, get all parts for this order to delete their history
                                parts_res = supabase.table("pecas").select("id_peca").eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                                if parts_res.data:
                                    part_ids = [p["id_peca"] for p in parts_res.data]
                                    # Delete history for all parts of this order
                                    supabase.table("historico_status").delete().in_("id_peca", part_ids).execute()
                                # Delete alerts related to this order
                                supabase.table("alerta_atraso").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                                # Delete parts
                                supabase.table("pecas").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                                # Delete order
                                supabase.table("ordem_pedido").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                                deleted_items.append(f"OP {candidate['data']['codigo_op']}")
                            else:
                                # Delete history for this part first
                                supabase.table("historico_status").delete().eq("id_peca", candidate["data"]["id_peca"]).execute()
                                # Delete part
                                supabase.table("pecas").delete().eq("id_peca", candidate["data"]["id_peca"]).execute()
                                deleted_items.append(f"Peça {candidate['data']['nome_peca']}")
                        
                        if len(deleted_items) == 1:
                            msg = format_delete_success(deleted_items[0])
                        else:
                            msg = f"✅ *Exclusão Realizada*\n\nOs seguintes itens foram removidos:\n" + "\n".join([f"• {item}" for item in deleted_items])
                        response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                    else:
                        msg, gen_tokens = generate_agent_response(message, {"status": "cancelled", "type": "delete"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                else:
                    # Search logic for delete
                    orders = []
                    parts = []
                    
                    # Ensure query is a string
                    if isinstance(query, list):
                        query = ", ".join(query)
                    
                    # Normalize query: replace ' e ' with ',', split by ','
                    clean_query = query.replace(" e ", ",").replace(" and ", ",")
                    query_parts = [q.strip() for q in clean_query.split(",") if q.strip()]
                    
                    if target in ["order", "any"]:
                        if len(query_parts) > 1:
                            # Multiple OPs - use ilike for case-insensitive matching
                            or_filter = ",".join([f"codigo_op.ilike.{qp}" for qp in query_parts])
                            orders = supabase.table("ordem_pedido").select("*").or_(or_filter).execute().data
                        elif query_parts:
                            # Single term
                            q = query_parts[0]
                            orders = supabase.table("ordem_pedido").select("*").or_(f"codigo_op.ilike.{q},nome_cliente.ilike.%{q}%").execute().data

                    if target in ["part", "any"]:
                        # Check UUIDs
                        valid_uuids = []
                        text_queries = []
                        for q in query_parts:
                            try:
                                uuid.UUID(q)
                                valid_uuids.append(q)
                            except ValueError:
                                text_queries.append(q)
                        
                        found_parts = []
                        
                        # 1. Search by UUIDs
                        if valid_uuids:
                            res = supabase.table("pecas").select("*").in_("id_peca", valid_uuids).execute()
                            found_parts.extend(res.data)
                            
                        # 2. Search by Name (using text queries)
                        if text_queries:
                            or_filter = ",".join([f"nome_peca.ilike.%{t}%" for t in text_queries])
                            res = supabase.table("pecas").select("*").or_(or_filter).execute()
                            found_parts.extend(res.data)
                            
                        # Deduplicate
                        seen_ids = set()
                        for p in found_parts:
                            if p["id_peca"] not in seen_ids:
                                parts.append(p)
                                seen_ids.add(p["id_peca"])
                    
                    total = len(orders) + len(parts)
                    if total == 1:
                        item = orders[0] if orders else parts[0]
                        item_type = "order" if orders else "part"
                        action_result = {"status": "confirmation_needed", "action": "delete", "item": item, "item_type": item_type}
                        msg = format_delete_confirmation("Pedido" if item_type == "order" else "Peça", item['codigo_op'] if item_type == "order" else item['nome_peca'], f"Cliente: {item['nome_cliente']}" if item_type == "order" else f"OP: {item['codigo_op']}")
                        response_obj = ChatResponse(response=msg, new_context={"awaiting_delete_confirmation": True, "delete_candidate": {"type": item_type, "data": item}}, tokens_used=total_tokens_used)
                    elif total == 0:
                        msg, gen_tokens = generate_agent_response(message, {"status": "not_found", "query": query, "action": "delete"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    elif total > 1 and len(orders) == total:
                        # Multiple orders found - allow batch delete
                        candidates = [{"type": "order", "data": o} for o in orders]
                        op_list = ", ".join([o['codigo_op'] for o in orders])
                        msg = f"🗑️ *Confirmar Exclusão em Lote*\n\nVocê está prestes a deletar {total} pedidos:\n"
                        for o in orders:
                            msg += f"• *OP:* {o['codigo_op']} | *Cliente:* {o['nome_cliente']}\n"
                        msg += "\n⚠️ Esta ação não pode ser desfeita. Confirmar? (Sim/Não)"
                        response_obj = ChatResponse(response=msg, new_context={"awaiting_delete_confirmation": True, "delete_candidates": candidates}, tokens_used=total_tokens_used)
                    elif total > 1 and len(parts) == total:
                        # Multiple parts found - allow batch delete
                        candidates = [{"type": "part", "data": p} for p in parts]
                        msg = f"🗑️ *Confirmar Exclusão em Lote*\n\nVocê está prestes a deletar {total} peças:\n"
                        for p in parts:
                            msg += f"• *Peça:* {p['nome_peca']} | *OP:* {p['codigo_op']}\n"
                        msg += "\n⚠️ Esta ação não pode ser desfeita. Confirmar? (Sim/Não)"
                        response_obj = ChatResponse(response=msg, new_context={"awaiting_delete_confirmation": True, "delete_candidates": candidates}, tokens_used=total_tokens_used)
                    else:
                        # Mixed results (orders and parts) - ask to be more specific
                        msg, gen_tokens = generate_agent_response(message, {"status": "multiple_found", "count": total, "query": query})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)

            # --- CREATE ORDER INTENT ---
            elif extraction.get("is_order_intent"):
                data = extraction.get("data")
                missing = extraction.get("missing_fields", [])
                
                # Check if this is a confirmation response for an existing pending order
                is_confirmation_response = any(k in message.lower() for k in ["sim", "s", "yes", "ok", "confirm", "pode", "confirmo"])
                is_cancel_response = any(k in message.lower() for k in ["não", "nao", "no", "cancel", "cancelar"])
                
                if state.get("awaiting_create_confirmation"):
                    if is_confirmation_response:
                        # User confirmed - use the stored pending data to create the order
                        pending_data = state.get("partial_data", data)
                        order_payload = {k: v for k, v in pending_data.items() if k != "pecas"}
                        codigo_op = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        order_payload["codigo_op"] = codigo_op
                        order_payload["status"] = "Em Produção"
                        # data_entrega permanece null até a entrega ser realizada
                        if not order_payload.get("data_entrega"): order_payload["data_entrega"] = None
                        if not order_payload.get("data_pedido"): order_payload["data_pedido"] = date.today().isoformat()
                        
                        supabase.table("ordem_pedido").insert(order_payload).execute()
                        
                        # Trigger n8n
                        trigger_n8n_webhook({"event": "new_order", "codigo_op": codigo_op, "data": order_payload})
                        
                        # Get parts from pending data or from current extraction
                        pending_parts = pending_data.get("pecas", []) or state.get("pending_parts", []) or extraction.get("parts_data", [])
                        
                        action_result = {
                            "status": "success", 
                            "action": "create_order", 
                            "codigo_op": codigo_op, 
                            "parts_found": pending_parts,
                            "message": "PEDIDO CRIADO COM SUCESSO."
                        }
                        
                        # Use the new template that shows parts if found
                        msg = format_order_created_success(codigo_op, pending_parts)
                        
                        # Set active order in context to allow adding parts next - clear awaiting_create_confirmation
                        # Store the pending parts for easy confirmation
                        new_context = {
                            "active_order_op": codigo_op, 
                            "partial_data": {}, 
                            "awaiting_create_confirmation": False,
                            "awaiting_parts_confirmation": True if pending_parts else False,
                            "pending_parts": pending_parts
                        }
                        response_obj = ChatResponse(response=msg, new_context=new_context, tokens_used=total_tokens_used)
                    
                    elif is_cancel_response:
                        msg, gen_tokens = generate_agent_response(message, {"status": "cancelled", "action": "create_order"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, new_context={"awaiting_create_confirmation": False, "partial_data": {}}, tokens_used=total_tokens_used)
                    
                    else:
                        # Not a clear confirmation/cancel - user might be providing new data for a different order
                        # If complete new data was provided, treat it as a new order request
                        if not missing and data:
                            # This is new complete data - ask for confirmation for THIS new order
                            action_result = {"status": "confirmation_needed", "action": "create_order", "data": data}
                            msg = format_order_confirmation(data)
                            response_obj = ChatResponse(response=msg, new_context={"awaiting_create_confirmation": True, "partial_data": data}, tokens_used=total_tokens_used)
                        else:
                            # User didn't confirm - remind them to confirm or cancel
                            msg = "Por favor, responda com *Sim* para confirmar a criação do pedido ou *Não* para cancelar."
                            response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                
                if not response_obj:
                    # Get any parts that were extracted alongside the order data
                    parts_from_extraction = extraction.get("parts_data", [])
                    
                    if not missing:
                        # All data present - ALWAYS ask for confirmation first
                        # Include parts in the partial_data so they show after confirmation
                        order_with_parts = {**data}
                        if parts_from_extraction:
                            order_with_parts["pecas"] = parts_from_extraction
                        
                        action_result = {"status": "confirmation_needed", "action": "create_order", "data": order_with_parts}
                        msg = format_order_confirmation(data)
                        response_obj = ChatResponse(response=msg, new_context={"awaiting_create_confirmation": True, "partial_data": order_with_parts}, tokens_used=total_tokens_used)
                    else:
                        # Missing data - ask for the missing fields
                        # Still preserve any parts found
                        order_with_parts = {**data}
                        if parts_from_extraction:
                            order_with_parts["pecas"] = parts_from_extraction
                        
                        if extraction.get("missing_message"):
                            response_obj = ChatResponse(response=extraction.get("missing_message"), new_context={"partial_data": order_with_parts, "awaiting_create_confirmation": False}, tokens_used=total_tokens_used)
                        else:
                            action_result = {"status": "missing_data", "missing_fields": missing, "current_data": data}
                            msg, gen_tokens = generate_agent_response(message, action_result)
                            total_tokens_used += gen_tokens
                            response_obj = ChatResponse(response=msg, new_context={"partial_data": order_with_parts, "awaiting_create_confirmation": False}, tokens_used=total_tokens_used)

            # --- ADD PARTS INTENT ---
            elif extraction.get("is_add_part_intent"):
                parts_data = extraction.get("parts_data", [])
                active_op = state.get("active_order_op")
                target_op = extraction.get("target_op")
                
                # If user specified an OP, use it. Otherwise fallback to context.
                if target_op:
                    active_op = target_op
                
                if not active_op:
                    msg, gen_tokens = generate_agent_response(message, {"status": "error", "message": "Para qual Ordem de Pedido (OP) você deseja adicionar peças? Por favor, informe o código da OP."})
                    total_tokens_used += gen_tokens
                    response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                elif not parts_data:
                    # Check if we have missing fields for parts
                    missing = extraction.get("missing_fields", [])
                    if missing:
                         response_obj = ChatResponse(response=extraction.get("missing_message", "Faltam dados para a peça."), tokens_used=total_tokens_used)
                    else:
                        msg, gen_tokens = generate_agent_response(message, {"status": "error", "message": "Não entendi quais peças adicionar."})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                else:
                    # Fetch order details for context
                    order_res = supabase.table("ordem_pedido").select("*").eq("codigo_op", active_op).execute()
                    if order_res.data:
                        order_info = order_res.data[0]
                        parts_payload = []
                        for p in parts_data:
                            p["codigo_op"] = active_op
                            p["status"] = "Pendente"
                            # Use client from order if not provided in part
                            if not p.get("nome_cliente"):
                                p["nome_cliente"] = order_info["nome_cliente"]
                            
                            p["previsao_entrega"] = order_info["previsao_entrega"]
                            p["data_entrega"] = None  # Será preenchido quando a entrega for realizada
                            p["pecas_produzidas"] = 0
                            parts_payload.append(p)
                        
                        supabase.table("pecas").insert(parts_payload).execute()
                        
                        action_result = {"status": "success", "action": "add_parts", "count": len(parts_payload), "codigo_op": active_op}
                        msg = f"✅ **Peças cadastradas com sucesso!**\n\nO sistema agora está monitorando esta produção."
                        # Keep active_op in context to allow adding more parts
                        response_obj = ChatResponse(response=msg, new_context={"active_order_op": active_op}, tokens_used=total_tokens_used)
                    else:
                        msg, gen_tokens = generate_agent_response(message, {"status": "error", "message": f"Pedido {active_op} não encontrado."})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)

            # --- UPDATE INTENT ---
            elif extraction.get("is_update_intent"):
                target = extraction.get("update_target") or "any"
                query = extraction.get("update_query")
                op_filter = extraction.get("codigo_op") # New field
                fields = extraction.get("update_fields", {})
                
                if state.get("awaiting_update_confirmation"):
                    if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                        candidate = state.get("update_candidate")
                        if candidate:
                            if candidate["type"] == "order":
                                supabase.table("ordem_pedido").update(candidate["fields"]).eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                            else:
                                supabase.table("pecas").update(candidate["fields"]).eq("id_peca", candidate["data"]["id_peca"]).execute()
                            
                            action_result = {"status": "success", "action": "update", "item": candidate["data"], "fields": candidate["fields"]}
                            msg = format_update_success(f"Pedido {candidate['data']['codigo_op']}" if candidate["type"] == "order" else f"Peça {candidate['data']['nome_peca']}")
                            response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                        else:
                            response_obj = ChatResponse(response="Erro: Contexto de atualização perdido.", tokens_used=total_tokens_used)
                    else:
                        msg, gen_tokens = generate_agent_response(message, {"status": "cancelled", "action": "update"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, new_context={}, tokens_used=total_tokens_used)
                else:
                    # Search logic for update
                    orders = []
                    parts = []
                    
                    # If no query, try to use context
                    if not query and state.get("last_active_item"):
                        last_item = state.get("last_active_item")
                        if last_item["type"] == "order":
                            orders = [last_item["data"]]
                        else:
                            parts = [last_item["data"]]
                    
                    elif query:
                        # Check if we have previous search results to filter from
                        last_results = state.get("last_search_results")
                        
                        import unicodedata
                        def normalize_text(text):
                            if not text: return ""
                            return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()

                        if last_results:
                            # Filter locally first
                            if target in ["part", "any"] and "parts" in last_results:
                                parts = [p for p in last_results["parts"] if normalize_text(query) in normalize_text(p["nome_peca"])]
                            if target in ["order", "any"] and "orders" in last_results:
                                orders = [o for o in last_results["orders"] if normalize_text(query) in normalize_text(o["nome_cliente"]) or normalize_text(query) in normalize_text(o["codigo_op"])]
                        
                        # If local filter didn't find anything (or no context), go to DB
                        if not parts and not orders:
                            if target in ["order", "any"]:
                                q = supabase.table("ordem_pedido").select("*").or_(f"codigo_op.ilike.{query},nome_cliente.ilike.%{query}%")
                                if op_filter: q = q.ilike("codigo_op", op_filter)
                                orders = q.execute().data
                                
                            if target in ["part", "any"]:
                                # Try exact match first for ID if query is UUID
                                try:
                                    uuid.UUID(query)
                                    parts = supabase.table("pecas").select("*").eq("id_peca", query).execute().data
                                except ValueError:
                                    # Not a UUID, search by name
                                    q = supabase.table("pecas").select("*").ilike("nome_peca", f"%{query}%")
                                    if op_filter: q = q.ilike("codigo_op", op_filter)
                                    parts = q.execute().data
                    
                    total = len(orders) + len(parts)
                    
                    if total == 1:
                        item = orders[0] if orders else parts[0]
                        item_type = "order" if orders else "part"
                        
                        action_result = {"status": "confirmation_needed", "action": "update", "item": item, "item_type": item_type, "fields": fields}
                        msg = format_update_confirmation("Pedido" if item_type == "order" else "Peça", item['codigo_op'] if item_type == "order" else item['nome_peca'], fields)
                        
                        response_obj = ChatResponse(
                            response=msg, 
                            new_context={
                                "awaiting_update_confirmation": True, 
                                "update_candidate": {"type": item_type, "data": item, "fields": fields}
                            },
                            tokens_used=total_tokens_used
                        )
                    elif total == 0:
                        msg, gen_tokens = generate_agent_response(message, {"status": "not_found", "query": query or "contexto", "action": "update"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)
                    else:
                        # Too many results
                        msg, gen_tokens = generate_agent_response(message, {"status": "multiple_found", "count": total, "query": query, "action": "update"})
                        total_tokens_used += gen_tokens
                        response_obj = ChatResponse(response=msg, tokens_used=total_tokens_used)

            # --- DEFAULT ---
            if not response_obj:
                # Fallback to conversational agent with history
                history_context = history_str_list[:-1] if history_str_list else []
                ai_response, chat_tokens = get_chat_response(message, history_context)
                total_tokens_used += chat_tokens
                response_obj = ChatResponse(response=ai_response, new_context=state, tokens_used=total_tokens_used)
                
        if phone:
            try:
                # 3. Update Session in Supabase
                
                # Append new messages to history object
                history_objs.append({"role": "user", "content": message})
                if response_obj and response_obj.response:
                    history_objs.append({"role": "assistant", "content": response_obj.response})
                
                # Keep only last 20 messages to avoid huge JSONs
                if len(history_objs) > 20:
                    history_objs = history_objs[-20:]
                
                # Update State - MERGE new context into existing state to preserve history
                if response_obj.new_context is not None:
                    new_state = {**state, **response_obj.new_context}
                else:
                    new_state = state
                
                # Upsert session
                supabase.table("chat_sessions").upsert({
                    "phone_number": phone,
                    "history": history_objs,
                    "state": new_state,
                    "updated_at": datetime.now().isoformat()
                }).execute()
                
            except Exception as e:
                print(f"Failed to save session to Supabase: {e}")
                
        return response_obj
    except Exception as e:
        print(f"CRITICAL ERROR in chat_endpoint: {e}")
        # DEBUG: Returning error details to user to identify the issue
        return ChatResponse(response=f"Desculpe, erro interno: {str(e)}")

@app.get("/context/{phone_number}")
def get_context(phone_number: str):
    """
    Debug endpoint to view the current context (history and state) for a user from Supabase.
    """
    supabase = get_supabase()
    try:
        res = supabase.table("chat_sessions").select("*").eq("phone_number", phone_number).execute()
        if res.data:
            return res.data[0]
        return {"message": "No session found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/n8n", response_model=ChatResponse)
def n8n_webhook(req: ChatRequest):
    """
    Webhook for n8n to send messages.
    Reuses the chat logic.
    """
    return chat_endpoint(req)

# --- CRUD for Catalog (Catálogo) ---
# Tabela: catalogo_pecas

@app.post("/catalogo", response_model=dict)
def create_catalog_item(item: CatalogoItemCreate):
    """
    Cria um novo item no catálogo.
    Tipos válidos: Produto Final, Itens Consumíveis, Matérias Primas, Inventário
    O campo tempo_producao é obrigatório apenas para itens do tipo 'Produto Final'.
    """
    supabase = get_supabase()
    
    # Validate tipo
    valid_types = TipoItemCatalogo.all_types()
    if item.tipo not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo inválido. Tipos válidos: {', '.join(valid_types)}"
        )
    
    # Validate tempo_producao for Produto Final
    if item.tipo == TipoItemCatalogo.PRODUTO_FINAL and not item.tempo_producao:
        raise HTTPException(
            status_code=400,
            detail="O campo 'tempo_producao' é obrigatório para itens do tipo 'Produto Final'"
        )
    
    try:
        item_data = {
            "nome": item.nome,
            "preco": item.preco,
            "tipo": item.tipo,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Add tempo_producao only for Produto Final
        if item.tipo == TipoItemCatalogo.PRODUTO_FINAL:
            item_data["tempo_producao"] = item.tempo_producao
        
        response = supabase.table("catalogo_pecas").insert(item_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Falha ao criar item no catálogo")
        
        return {
            "id": response.data[0]["id"],
            "message": f"Item '{item.nome}' criado com sucesso no catálogo"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/catalogo")
def list_catalog_items(tipo: str = None, query: str = None):
    """
    Lista itens do catálogo.
    Pode filtrar por tipo e/ou buscar por nome.
    """
    supabase = get_supabase()
    
    try:
        q = supabase.table("catalogo_pecas").select("*")
        
        # Filter by tipo if provided
        if tipo:
            valid_types = TipoItemCatalogo.all_types()
            if tipo not in valid_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo inválido. Tipos válidos: {', '.join(valid_types)}"
                )
            q = q.eq("tipo", tipo)
        
        # Search by name if query provided
        if query:
            q = q.ilike("nome", f"%{query}%")
        
        # Order by created_at descending
        response = q.order("created_at", desc=True).execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/catalogo/tipos")
def get_catalog_types():
    """
    Retorna os tipos de itens disponíveis no catálogo.
    """
    return {
        "tipos": TipoItemCatalogo.all_types(),
        "descricao": {
            "Produto Final": "Peças e produtos que a empresa produz (requer tempo de produção)",
            "Itens Consumíveis": "Materiais de consumo como parafusos, fitas, etc.",
            "Matérias Primas": "Materiais brutos usados na produção",
            "Inventário": "Outros itens em estoque"
        }
    }

@app.get("/catalogo/{item_id}")
def get_catalog_item(item_id: str):
    """
    Busca um item específico do catálogo pelo ID.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("catalogo_pecas").select("*").eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Item não encontrado no catálogo")
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/catalogo/{item_id}")
def update_catalog_item(item_id: str, item_update: dict):
    """
    Atualiza um item do catálogo.
    Campos atualizáveis: nome, preco, tipo, tempo_producao
    """
    supabase = get_supabase()
    
    try:
        # Validate tipo if being updated
        if "tipo" in item_update:
            valid_types = TipoItemCatalogo.all_types()
            if item_update["tipo"] not in valid_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tipo inválido. Tipos válidos: {', '.join(valid_types)}"
                )
            
            # If changing to Produto Final, tempo_producao becomes required
            if item_update["tipo"] == TipoItemCatalogo.PRODUTO_FINAL:
                # Check if tempo_producao is being provided or already exists
                if "tempo_producao" not in item_update:
                    # Fetch current item to check
                    current = supabase.table("catalogo_pecas").select("tempo_producao").eq("id", item_id).execute()
                    if current.data and not current.data[0].get("tempo_producao"):
                        raise HTTPException(
                            status_code=400,
                            detail="O campo 'tempo_producao' é obrigatório para itens do tipo 'Produto Final'"
                        )
        
        # Add updated_at timestamp
        item_update["updated_at"] = datetime.now().isoformat()
        
        response = supabase.table("catalogo_pecas").update(item_update).eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Item não encontrado ou não atualizado")
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/catalogo/{item_id}")
def delete_catalog_item(item_id: str):
    """
    Remove um item do catálogo.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("catalogo_pecas").delete().eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Item não encontrado no catálogo")
        
        return {"message": "Item removido do catálogo com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/catalogo/stats/resumo")
def get_catalog_stats():
    """
    Retorna estatísticas do catálogo: quantidade e valor total por tipo.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("catalogo_pecas").select("*").execute()
        items = response.data
        
        stats = {
            "total_itens": len(items),
            "valor_total": sum(float(item["preco"]) for item in items),
            "por_tipo": {}
        }
        
        for tipo in TipoItemCatalogo.all_types():
            tipo_items = [item for item in items if item["tipo"] == tipo]
            stats["por_tipo"][tipo] = {
                "quantidade": len(tipo_items),
                "valor_total": sum(float(item["preco"]) for item in tipo_items)
            }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- CRUD for Stock (Estoque) ---
# Tabela: estoque
# O estoque armazena quantidades de itens que existem no catálogo

@app.post("/estoque", response_model=dict)
def add_to_stock(item: EstoqueItemCreate):
    """
    Adiciona um item ao estoque.
    IMPORTANTE: O item deve existir no catálogo antes de ser adicionado ao estoque.
    Se já existir no estoque, a quantidade é atualizada (somada).
    """
    supabase = get_supabase()
    
    try:
        # 1. Verificar se o item existe no catálogo
        catalog_result = supabase.table("catalogo_pecas").select("*").ilike("nome", f"%{item.nome}%").execute()
        
        if not catalog_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Item '{item.nome}' não encontrado no catálogo. Cadastre-o primeiro no catálogo."
            )
        
        catalog_item = catalog_result.data[0]
        
        # 2. Verificar se já existe no estoque
        stock_result = supabase.table("estoque").select("*").ilike("nome", catalog_item["nome"]).execute()
        
        if stock_result.data:
            # Item já existe no estoque - somar quantidade
            existing = stock_result.data[0]
            new_quantity = existing["quantidade"] + item.quantidade
            
            update_result = supabase.table("estoque").update({
                "quantidade": new_quantity,
                "updated_at": datetime.now().isoformat()
            }).eq("id", existing["id"]).execute()
            
            return {
                "id": existing["id"],
                "message": f"Quantidade atualizada: {existing['quantidade']} + {item.quantidade} = {new_quantity}",
                "acao": "atualizado"
            }
        else:
            # Criar novo item no estoque
            stock_data = {
                "nome": catalog_item["nome"],
                "quantidade": item.quantidade,
                "preco_unitario": catalog_item["preco"],
                "tipo": catalog_item["tipo"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            insert_result = supabase.table("estoque").insert(stock_data).execute()
            
            if not insert_result.data:
                raise HTTPException(status_code=500, detail="Falha ao adicionar item ao estoque")
            
            return {
                "id": insert_result.data[0]["id"],
                "message": f"Item '{catalog_item['nome']}' adicionado ao estoque com {item.quantidade} unidades",
                "acao": "criado"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estoque")
def list_stock_items(tipo: str = None, query: str = None):
    """
    Lista itens do estoque.
    Pode filtrar por tipo e/ou buscar por nome.
    """
    supabase = get_supabase()
    
    try:
        q = supabase.table("estoque").select("*")
        
        if tipo:
            q = q.eq("tipo", tipo)
        
        if query:
            q = q.ilike("nome", f"%{query}%")
        
        response = q.order("nome").execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estoque/{item_id}")
def get_stock_item(item_id: str):
    """
    Busca um item específico do estoque pelo ID.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("estoque").select("*").eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Item não encontrado no estoque")
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/estoque/{item_id}")
def update_stock_quantity(item_id: str, update: EstoqueItemUpdate):
    """
    Atualiza a quantidade de um item no estoque.
    Operações: 'set' (definir), 'add' (somar), 'subtract' (subtrair)
    """
    supabase = get_supabase()
    
    try:
        # Buscar item atual
        current = supabase.table("estoque").select("*").eq("id", item_id).execute()
        
        if not current.data:
            raise HTTPException(status_code=404, detail="Item não encontrado no estoque")
        
        current_qty = current.data[0]["quantidade"]
        
        # Calcular nova quantidade baseado na operação
        if update.operacao == "add":
            new_qty = current_qty + update.quantidade
        elif update.operacao == "subtract":
            new_qty = current_qty - update.quantidade
            if new_qty < 0:
                raise HTTPException(status_code=400, detail="Quantidade insuficiente no estoque")
        else:  # "set"
            new_qty = update.quantidade
        
        # Atualizar
        response = supabase.table("estoque").update({
            "quantidade": new_qty,
            "updated_at": datetime.now().isoformat()
        }).eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Falha ao atualizar estoque")
        
        return {
            "id": item_id,
            "quantidade_anterior": current_qty,
            "quantidade_nova": new_qty,
            "operacao": update.operacao
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/estoque/{item_id}")
def delete_stock_item(item_id: str):
    """
    Remove um item do estoque.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("estoque").delete().eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Item não encontrado no estoque")
        
        return {"message": "Item removido do estoque com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estoque/stats/resumo")
def get_stock_stats():
    """
    Retorna estatísticas do estoque: quantidade total e valor por tipo.
    """
    supabase = get_supabase()
    
    try:
        response = supabase.table("estoque").select("*").execute()
        items = response.data
        
        stats = {
            "total_itens": len(items),
            "total_unidades": sum(item["quantidade"] for item in items),
            "valor_total": sum(float(item["preco_unitario"]) * item["quantidade"] for item in items),
            "por_tipo": {}
        }
        
        for tipo in TipoItemCatalogo.all_types():
            tipo_items = [item for item in items if item["tipo"] == tipo]
            stats["por_tipo"][tipo] = {
                "quantidade_itens": len(tipo_items),
                "total_unidades": sum(item["quantidade"] for item in tipo_items),
                "valor_total": sum(float(item["preco_unitario"]) * item["quantidade"] for item in tipo_items)
            }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estoque/verificar/{nome}")
def check_stock_availability(nome: str):
    """
    Verifica se um item existe no catálogo e no estoque.
    Útil para validar antes de adicionar ao estoque.
    """
    supabase = get_supabase()
    
    try:
        # Buscar no catálogo
        catalog_result = supabase.table("catalogo_pecas").select("*").ilike("nome", f"%{nome}%").execute()
        
        # Buscar no estoque
        stock_result = supabase.table("estoque").select("*").ilike("nome", f"%{nome}%").execute()
        
        return {
            "nome_pesquisado": nome,
            "existe_no_catalogo": len(catalog_result.data) > 0,
            "itens_catalogo": catalog_result.data,
            "existe_no_estoque": len(stock_result.data) > 0,
            "itens_estoque": stock_result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
