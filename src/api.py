from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from typing import List
import uuid
from datetime import datetime, date
import random
import string

from src.models import OrderCreate, PartsListCreate, OrdemPedido, Peca, AlertaAtraso
from src.models import OrderCreate, PartsListCreate, OrdemPedido, Peca, AlertaAtraso
from src.database import get_supabase
import os
import requests
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import tools for the agent logic
from src.tools import (
    extract_data_from_message,
    extract_parts_from_message,
    extract_text_from_pdf,
    extract_data_with_ai,
    generate_agent_response
)

app = FastAPI(title="Production Monitoring API")

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = [] # [{"role": "user", "content": "..."}, ...]
    context: Optional[Dict[str, Any]] = None # To pass state back and forth if needed

class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None # "create_order", "search", etc.
    data: Optional[Dict[str, Any]] = None # Data associated with the action
    new_context: Optional[Dict[str, Any]] = None # Updated context to be sent back in next request

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
    if not order_data.get("previsao_entrega"):
        order_data["previsao_entrega"] = order_data["data_entrega"]
    
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
            part_dict["data_entrega"] = order_info["data_entrega"]
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
            
            # Parse dates
            data_entrega = datetime.strptime(part["data_entrega"], "%Y-%m-%d").date()
            
            # Logic 1: Delay (Today > Delivery Date)
            if today > data_entrega:
                alert_reason = f"Atraso na entrega (Era para {data_entrega})"
            
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
                    order_res = supabase.table("ordem_pedido").select("data_pedido, data_entrega").eq("codigo_op", part["codigo_op"]).execute()
                    if order_res.data:
                        o = order_res.data[0]
                        d_pedido = datetime.strptime(o["data_pedido"], "%Y-%m-%d").date()
                        d_entrega = datetime.strptime(o["data_entrega"], "%Y-%m-%d").date()
                        
                        total_days = (d_entrega - d_pedido).days
                        if total_days > 0:
                            elapsed = (today - d_pedido).days
                            if (elapsed / total_days) > 0.5:
                                alert_reason = "Baixa produção (<70%) com >50% do prazo decorrido"

            if alert_reason:
                # Check if alert already exists to avoid duplicates (optional but good)
                # For MVP, just insert.
                
                alert_data = {
                    "nome_cliente": part["nome_cliente"],
                    "data_entrega": part["data_entrega"],
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
        # First delete parts associated with this order
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
    Intelligent endpoint that processes user messages, identifies intents,
    and executes actions (Search, Create, Update, Delete).
    Designed to work with n8n.
    """
    supabase = get_supabase()
    message = req.message
    history = req.history
    context = req.context or {}
    
    # 1. Analyze the message using the AI tool
    # We pass the current context data if we are in the middle of a flow
    current_data = context.get("partial_data")
    
    extraction = extract_data_from_message(message, current_data, history)
    
    if not extraction:
        return ChatResponse(response="Desculpe, tive um erro interno ao processar sua mensagem.")

    # 2. Handle Intents
    
    # --- SEARCH INTENT ---
    if extraction.get("is_search_intent"):
        query = extraction.get("search_query")
        if not query:
            return ChatResponse(response="O que você deseja buscar?")
            
        # Perform search (logic adapted from streamlit app)
        # Search Orders
        orders_res = supabase.table("ordem_pedido").select("*").or_(f"nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
        orders = orders_res.data
        
        # Search Parts
        parts_res = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{query}%,nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
        parts = parts_res.data
        
        if not orders and not parts:
            msg = generate_agent_response(message, {"status": "not_found", "query": query})
            return ChatResponse(response=msg)
            
        # Let the AI format the search results
        action_result = {
            "status": "success",
            "type": "search_results",
            "query": query,
            "orders": orders,
            "parts": parts
        }
        msg = generate_agent_response(message, action_result)
                
        return ChatResponse(response=msg, action="search_result", data={"orders": orders, "parts": parts})

    # --- DELETE INTENT ---
    elif extraction.get("is_delete_intent"):
        target = extraction.get("delete_target")
        query = extraction.get("delete_query")
        
        # Check if we are confirming a deletion
        if context.get("awaiting_delete_confirmation"):
            if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                candidate = context.get("delete_candidate")
                if candidate["type"] == "order":
                    # Delete parts first
                    supabase.table("pecas").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                    supabase.table("ordem_pedido").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                else:
                    supabase.table("pecas").delete().eq("id_peca", candidate["data"]["id_peca"]).execute()
                
                msg = generate_agent_response(message, {"status": "success", "type": "delete", "item": candidate})
                return ChatResponse(response=msg, new_context={})
            else:
                msg = generate_agent_response(message, {"status": "cancelled", "type": "delete"})
                return ChatResponse(response=msg, new_context={})

        # Search for item to delete
        orders = []
        parts = []
        if target in ["order", "any"]:
            orders = supabase.table("ordem_pedido").select("*").or_(f"codigo_op.eq.{query},nome_cliente.ilike.%{query}%").execute().data
        if target in ["part", "any"]:
            parts = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{query}%,id_peca.eq.{query}").execute().data
            
        total = len(orders) + len(parts)
        
        if total == 0:
            msg = generate_agent_response(message, {"status": "not_found", "query": query, "action": "delete"})
            return ChatResponse(response=msg)
        elif total == 1:
            item = orders[0] if orders else parts[0]
            item_type = "order" if orders else "part"
            
            action_result = {
                "status": "confirmation_needed",
                "action": "delete",
                "item": item,
                "item_type": item_type
            }
            
            msg = generate_agent_response(message, action_result)
            
            return ChatResponse(
                response=msg,
                new_context={
                    "awaiting_delete_confirmation": True,
                    "delete_candidate": {"type": item_type, "data": item}
                }
            )
        else:
            msg = generate_agent_response(message, {"status": "multiple_found", "count": total, "query": query})
            return ChatResponse(response=msg)

    # --- CREATE ORDER INTENT ---
    elif extraction.get("is_order_intent"):
        data = extraction.get("data")
        missing = extraction.get("missing_fields", [])
        
        # Check if user is confirming creation
        if context.get("awaiting_create_confirmation") and not missing:
            if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                # Create Order
                order_payload = {k: v for k, v in data.items() if k != "pecas"}
                
                # Generate OP code
                codigo_op = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                order_payload["codigo_op"] = codigo_op
                order_payload["status"] = "Em Produção"
                if not order_payload.get("previsao_entrega"):
                    order_payload["previsao_entrega"] = order_payload["data_entrega"]
                
                supabase.table("ordem_pedido").insert(order_payload).execute()
                
                # Create Parts
                created_parts_count = 0
                if "pecas" in data and data["pecas"]:
                    parts_payload = []
                    for p in data["pecas"]:
                        p["codigo_op"] = codigo_op
                        p["status"] = "Pendente"
                        p["nome_cliente"] = order_payload["nome_cliente"]
                        p["data_entrega"] = order_payload["data_entrega"]
                        p["pecas_produzidas"] = 0
                        parts_payload.append(p)
                    
                    supabase.table("pecas").insert(parts_payload).execute()
                    created_parts_count = len(parts_payload)
                
                # Trigger n8n
                trigger_n8n_webhook({"event": "new_order", "codigo_op": codigo_op, "data": order_payload})
                
                action_result = {
                    "status": "success",
                    "action": "create_order",
                    "codigo_op": codigo_op,
                    "parts_count": created_parts_count
                }
                msg = generate_agent_response(message, action_result)
                
                return ChatResponse(
                    response=msg,
                    new_context={}
                )
            elif any(k in message.lower() for k in ["não", "nao", "cancel"]):
                msg = generate_agent_response(message, {"status": "cancelled", "action": "create_order"})
                return ChatResponse(response=msg, new_context={})

        if not missing:
            # All data present, ask for confirmation
            action_result = {
                "status": "confirmation_needed",
                "action": "create_order",
                "data": data
            }
            msg = generate_agent_response(message, action_result)
            
            return ChatResponse(
                response=msg,
                new_context={
                    "awaiting_create_confirmation": True,
                    "partial_data": data
                }
            )
        else:
            # Missing data
            # Use the missing_message from extraction if available, otherwise ask AI to generate
            if extraction.get("missing_message"):
                return ChatResponse(
                    response=extraction.get("missing_message"),
                    new_context={"partial_data": data}
                )
            
            action_result = {
                "status": "missing_data",
                "missing_fields": missing,
                "current_data": data
            }
            msg = generate_agent_response(message, action_result)
            return ChatResponse(
                response=msg,
                new_context={"partial_data": data}
            )

    # --- DEFAULT / FALLBACK ---
    msg = generate_agent_response(message, {"status": "unknown_intent", "message": "Não entendi a intenção."})
    return ChatResponse(
        response=msg,
        new_context=context
    )
