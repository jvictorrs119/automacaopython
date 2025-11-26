import requests
import json

API_URL = "http://localhost:8000"

def test_search():
    print("Testing Search...")
    
    # 1. Create Order with Parts
    print("Creating Order with Parts...")
    order_data = {
        "nome_cliente": "Search Test",
        "numero_pedido": 999,
        "data_pedido": "2025-01-01",
        "preco_total": 100.0,
        "data_entrega": "2025-01-10",
        "icms": 0.0
    }
    res = requests.post(f"{API_URL}/orders", json=order_data)
    op_code = res.json()["codigo_op"]
    print(f"Created OP: {op_code}")
    
    parts_data = {
        "codigo_op": op_code,
        "pecas": [
            {"nome_peca": "Part A", "quantidade": 10, "preco_unitario": 5.0},
            {"nome_peca": "Part B", "quantidade": 5, "preco_unitario": 10.0}
        ]
    }
    requests.post(f"{API_URL}/parts", json=parts_data)
    
    # 2. Search by OP Code
    print(f"Searching for '{op_code}'...")
    res = requests.get(f"{API_URL}/parts/search", params={"query": op_code})
    parts = res.json()
    print(f"Found {len(parts)} parts.")
    for p in parts:
        print(f" - {p['nome_peca']} ({p['codigo_op']})")
        
    if len(parts) == 0:
        print("FAIL: No parts found by OP code.")
    else:
        print("SUCCESS: Parts found.")

if __name__ == "__main__":
    test_search()
