import requests
import json

API_URL = "http://localhost:8000"

def dump_db():
    print("Dumping DB...")
    
    # Get all orders
    res = requests.get(f"{API_URL}/orders")
    orders = res.json()
    print(f"Orders: {len(orders)}")
    for o in orders:
        print(f"OP: {o['codigo_op']} | Client: {o['nome_cliente']}")
        
    # Get all parts
    res = requests.get(f"{API_URL}/parts/search") # Empty query returns all (limit 50)
    parts = res.json()
    print(f"Parts: {len(parts)}")
    for p in parts:
        print(f"Part: {p['nome_peca']} | OP: {p['codigo_op']}")

if __name__ == "__main__":
    dump_db()
