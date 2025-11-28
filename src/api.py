from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from typing import List
import uuid
from datetime import datetime, date
import random
import string

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
    extract_data_with_ai,
    generate_agent_response
)
from src.redis_client import get_redis_client
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
    Intelligent endpoint that processes user messages.
    If 'phone_number' is provided, it automatically manages context in Redis.
    """
    redis_client = get_redis_client()
    message = req.message
    phone = req.phone_number
    
    # 1. Load Context and History from Redis
    history = []
    state = {}
    
    if phone and redis_client:
        try:
            # Load history (List of strings)
            # lrange 0 -1 gets all elements
            raw_history = redis_client.lrange(f"chat:{phone}:history", 0, -1)
            history = [h.decode("utf-8") if isinstance(h, bytes) else h for h in raw_history]
            
            # Load state (JSON string)
            state_json = redis_client.get(f"chat:{phone}:state")
            if state_json:
                state = json.loads(state_json)
        except Exception as e:
            print(f"Failed to load context from Redis: {e}")

    # Append current user message to history for the tool (and storage)
    user_msg_str = f"USER: {message}"
    
    # We add it to the local history list for the tool to see context
    # Note: The tool prompt separates history and current message, but we'll follow the flow.
    # Actually, let's keep the history passed to the tool as the *previous* history + current?
    # The original code appended it.
    history.append(user_msg_str)
    
    # 2. Analyze Message
    current_data = state.get("partial_data")
    
    # Extract data using the history (which now contains strings)
    extraction = extract_data_from_message(message, current_data, history)
    
    response_obj = None
    
    if not extraction:
        response_obj = ChatResponse(response="Desculpe, tive um erro interno.")
    else:
        # --- SEARCH INTENT ---
        if extraction.get("is_search_intent"):
            query = extraction.get("search_query")
            if not query:
                response_obj = ChatResponse(response="O que você deseja buscar?")
            else:
                supabase = get_supabase()
                orders_res = supabase.table("ordem_pedido").select("*").or_(f"nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
                parts_res = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{query}%,nome_cliente.ilike.%{query}%,codigo_op.ilike.%{query}%,status.ilike.%{query}%").execute()
                
                orders = orders_res.data
                parts = parts_res.data
                
                if not orders and not parts:
                    msg = generate_agent_response(message, {"status": "not_found", "query": query})
                    response_obj = ChatResponse(response=msg)
                else:
                    action_result = {"status": "success", "type": "search_results", "query": query, "orders": orders, "parts": parts}
                    msg = generate_agent_response(message, action_result)
                    response_obj = ChatResponse(response=msg, action="search_result", data={"orders": orders, "parts": parts})

        # --- DELETE INTENT ---
        elif extraction.get("is_delete_intent"):
            supabase = get_supabase()
            target = extraction.get("delete_target")
            query = extraction.get("delete_query")
            
            if state.get("awaiting_delete_confirmation"):
                if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                    candidate = state.get("delete_candidate")
                    if candidate["type"] == "order":
                        supabase.table("pecas").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                        supabase.table("ordem_pedido").delete().eq("codigo_op", candidate["data"]["codigo_op"]).execute()
                    else:
                        supabase.table("pecas").delete().eq("id_peca", candidate["data"]["id_peca"]).execute()
                    
                    msg = generate_agent_response(message, {"status": "success", "type": "delete", "item": candidate})
                    response_obj = ChatResponse(response=msg, new_context={})
                else:
                    msg = generate_agent_response(message, {"status": "cancelled", "type": "delete"})
                    response_obj = ChatResponse(response=msg, new_context={})
            else:
                # Search logic for delete
                orders = []
                parts = []
                if target in ["order", "any"]:
                    orders = supabase.table("ordem_pedido").select("*").or_(f"codigo_op.eq.{query},nome_cliente.ilike.%{query}%").execute().data
                if target in ["part", "any"]:
                    parts = supabase.table("pecas").select("*").or_(f"nome_peca.ilike.%{query}%,id_peca.eq.{query}").execute().data
                
                total = len(orders) + len(parts)
                if total == 1:
                    item = orders[0] if orders else parts[0]
                    item_type = "order" if orders else "part"
                    action_result = {"status": "confirmation_needed", "action": "delete", "item": item, "item_type": item_type}
                    msg = generate_agent_response(message, action_result)
                    response_obj = ChatResponse(response=msg, new_context={"awaiting_delete_confirmation": True, "delete_candidate": {"type": item_type, "data": item}})
                elif total == 0:
                    msg = generate_agent_response(message, {"status": "not_found", "query": query, "action": "delete"})
                    response_obj = ChatResponse(response=msg)
                else:
                    msg = generate_agent_response(message, {"status": "multiple_found", "count": total, "query": query})
                    response_obj = ChatResponse(response=msg)

        # --- CREATE ORDER INTENT ---
        elif extraction.get("is_order_intent"):
            supabase = get_supabase()
            data = extraction.get("data")
            missing = extraction.get("missing_fields", [])
            
            if state.get("awaiting_create_confirmation") and not missing:
                if any(k in message.lower() for k in ["sim", "s", "yes", "confirm"]):
                    # Create logic (Order Only)
                    order_payload = {k: v for k, v in data.items() if k != "pecas"}
                    codigo_op = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    order_payload["codigo_op"] = codigo_op
                    order_payload["status"] = "Em Produção"
                    if not order_payload.get("previsao_entrega"): order_payload["previsao_entrega"] = order_payload["data_entrega"]
                    
                    supabase.table("ordem_pedido").insert(order_payload).execute()
                    
                    # Trigger n8n
                    trigger_n8n_webhook({"event": "new_order", "codigo_op": codigo_op, "data": order_payload})
                    
                    action_result = {"status": "success", "action": "create_order", "codigo_op": codigo_op, "message": "Order created. Now asking for parts."}
                    msg = generate_agent_response(message, action_result)
                    
                    # Set active order in context to allow adding parts next
                    response_obj = ChatResponse(response=msg, new_context={"active_order_op": codigo_op, "partial_data": {}})
                elif any(k in message.lower() for k in ["não", "nao", "cancel"]):
                    msg = generate_agent_response(message, {"status": "cancelled", "action": "create_order"})
                    response_obj = ChatResponse(response=msg, new_context={})
                else:
                     pass

            if not response_obj:
                if not missing:
                    action_result = {"status": "confirmation_needed", "action": "create_order", "data": data}
                    msg = generate_agent_response(message, action_result)
                    response_obj = ChatResponse(response=msg, new_context={"awaiting_create_confirmation": True, "partial_data": data})
                else:
                    if extraction.get("missing_message"):
                        response_obj = ChatResponse(response=extraction.get("missing_message"), new_context={"partial_data": data})
                    else:
                        action_result = {"status": "missing_data", "missing_fields": missing, "current_data": data}
                        msg = generate_agent_response(message, action_result)
                        response_obj = ChatResponse(response=msg, new_context={"partial_data": data})

        # --- ADD PARTS INTENT ---
        elif extraction.get("is_add_part_intent"):
            supabase = get_supabase()
            parts_data = extraction.get("parts_data", [])
            active_op = state.get("active_order_op")
            
            if not active_op:
                # Try to find if user mentioned an OP in the message, otherwise fail
                msg = generate_agent_response(message, {"status": "error", "message": "Nenhum pedido ativo para adicionar peças."})
                response_obj = ChatResponse(response=msg)
            elif not parts_data:
                msg = generate_agent_response(message, {"status": "error", "message": "Não entendi quais peças adicionar."})
                response_obj = ChatResponse(response=msg)
            else:
                # Fetch order details for context
                order_res = supabase.table("ordem_pedido").select("*").eq("codigo_op", active_op).execute()
                if order_res.data:
                    order_info = order_res.data[0]
                    parts_payload = []
                    for p in parts_data:
                        p["codigo_op"] = active_op
                        p["status"] = "Pendente"
                        p["nome_cliente"] = order_info["nome_cliente"]
                        p["data_entrega"] = order_info["data_entrega"]
                        p["pecas_produzidas"] = 0
                        parts_payload.append(p)
                    
                    supabase.table("pecas").insert(parts_payload).execute()
                    
                    action_result = {"status": "success", "action": "add_parts", "count": len(parts_payload), "codigo_op": active_op}
                    msg = generate_agent_response(message, action_result)
                    # Keep active_op in context to allow adding more parts
                    response_obj = ChatResponse(response=msg, new_context={"active_order_op": active_op})
                else:
                    msg = generate_agent_response(message, {"status": "error", "message": "Pedido não encontrado."})
                    response_obj = ChatResponse(response=msg, new_context={})

        # --- DEFAULT ---
        if not response_obj:
            msg = generate_agent_response(message, {"status": "unknown_intent", "message": "Não entendi a intenção."})
            response_obj = ChatResponse(response=msg, new_context=state)
    if phone and redis_client:
        try:
            # 3a. Update History
            # We need to push the user message and the assistant response
            # Since we already appended user_msg_str to the local 'history' variable, we need to be careful not to duplicate if we were using it for something else, 
            # but for Redis we just push.
            
            # Push User Message
            redis_client.rpush(f"chat:{phone}:history", user_msg_str)
            
            # Push Assistant Response
            assistant_msg_str = f"ASSISTANT: {response_obj.response}"
            redis_client.rpush(f"chat:{phone}:history", assistant_msg_str)
            
            # Trim to last 5 messages
            # LTRIM key start stop. We want last 5.
            # -5 is the 5th from the end. -1 is the last.
            redis_client.ltrim(f"chat:{phone}:history", -5, -1)
            
            # 3b. Update State
            new_state = response_obj.new_context if response_obj.new_context is not None else state
            redis_client.set(f"chat:{phone}:state", json.dumps(new_state))
            
        except Exception as e:
            print(f"Failed to save context to Redis: {e}")
            
    return response_obj

@app.get("/context/{phone_number}")
def get_context(phone_number: str):
    """
    Debug endpoint to view the current context (history and state) for a user.
    """
    redis_client = get_redis_client()
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis unavailable")
        
    try:
        history = redis_client.lrange(f"chat:{phone_number}:history", 0, -1)
        state_json = redis_client.get(f"chat:{phone_number}:state")
        state = json.loads(state_json) if state_json else {}
        
        return {
            "phone_number": phone_number,
            "history": history,
            "state": state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/n8n", response_model=ChatResponse)
def n8n_webhook(req: ChatRequest):
    """
    Webhook for n8n to send messages.
    Reuses the chat logic.
    """
    return chat_endpoint(req)
