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

app = FastAPI(title="Production Monitoring API")

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
        
        # Trigger n8n automation for parts
        trigger_n8n_webhook({
            "event": "new_parts",
            "codigo_op": parts_list.codigo_op,
            "count": len(parts_data),
            "parts": parts_data
        })

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
