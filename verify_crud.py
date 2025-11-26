import requests
import json
from datetime import date

API_URL = "http://localhost:8000"

def test_crud():
    print("Testing CRUD operations...")
    
    # 1. Create Order
    order_data = {
        "nome_cliente": "Test Client",
        "numero_pedido": 12345,
        "data_pedido": str(date.today()),
        "preco_total": 100.0,
        "data_entrega": str(date.today()),
        "icms": 18.0,
        "previsao_entrega": str(date.today())
    }
    
    print(f"Creating order: {order_data}")
    res = requests.post(f"{API_URL}/orders", json=order_data)
    if res.status_code != 200:
        print(f"Failed to create order: {res.text}")
        return
    
    order_res = res.json()
    codigo_op = order_res["codigo_op"]
    print(f"Order created with OP: {codigo_op}")
    
    # 2. Get Order
    print(f"Getting order {codigo_op}...")
    res = requests.get(f"{API_URL}/orders/{codigo_op}")
    if res.status_code != 200:
        print(f"Failed to get order: {res.text}")
        return
    print(f"Order retrieved: {res.json()['nome_cliente']}")
    
    # 3. Update Order
    print(f"Updating order {codigo_op}...")
    update_data = {"nome_cliente": "Updated Client"}
    res = requests.put(f"{API_URL}/orders/{codigo_op}", json=update_data)
    if res.status_code != 200:
        print(f"Failed to update order: {res.text}")
        return
    print(f"Order updated: {res.json()['nome_cliente']}")
    
    # 4. Create Part
    print("Creating part...")
    parts_data = {
        "codigo_op": codigo_op,
        "pecas": [
            {
                "nome_peca": "Test Part",
                "quantidade": 10,
                "preco_unitario": 5.0
            }
        ]
    }
    res = requests.post(f"{API_URL}/parts", json=parts_data)
    if res.status_code != 200:
        print(f"Failed to create parts: {res.text}")
        return
    print("Parts created.")
    
    # 5. Get Parts
    print(f"Getting parts for order {codigo_op}...")
    res = requests.get(f"{API_URL}/orders/{codigo_op}/parts")
    if res.status_code != 200:
        print(f"Failed to get parts: {res.text}")
        return
    parts = res.json()
    print(f"Parts retrieved: {len(parts)}")
    part_id = parts[0]["id_peca"]
    
    # 6. Update Part
    print(f"Updating part {part_id}...")
    part_update = {"quantidade": 20}
    res = requests.put(f"{API_URL}/parts/{part_id}", json=part_update)
    if res.status_code != 200:
        print(f"Failed to update part: {res.text}")
        return
    print(f"Part updated: {res.json()['quantidade']}")
    
    # 7. Delete Part
    print(f"Deleting part {part_id}...")
    res = requests.delete(f"{API_URL}/parts/{part_id}")
    if res.status_code != 200:
        print(f"Failed to delete part: {res.text}")
        return
    print("Part deleted.")
    
    # 8. Delete Order
    print(f"Deleting order {codigo_op}...")
    res = requests.delete(f"{API_URL}/orders/{codigo_op}")
    if res.status_code != 200:
        print(f"Failed to delete order: {res.text}")
        return
    print("Order deleted.")
    
    print("CRUD verification successful!")

if __name__ == "__main__":
    test_crud()
