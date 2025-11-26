import os
import requests
import json
from datetime import date
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def extract_text_from_pdf(uploaded_file):
    """Extract text from PDF file"""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_data_with_ai(pdf_text):
    """Use GPT-4.1-mini to extract structured data from PDF text"""
    
    prompt = f"""Você é um assistente especializado em extrair informações de pedidos de produção.

Analise o texto do PDF abaixo e extraia as seguintes informações em formato JSON:

- nome_cliente: Nome do cliente
- numero_pedido: Número do pedido (inteiro)
- data_pedido: Data do pedido (formato YYYY-MM-DD)
- preco_total: Preço total (número decimal)
- data_entrega: Data de entrega (formato YYYY-MM-DD)
- icms: Valor do ICMS em porcentagem (número decimal)
- previsao_entrega: Previsão de entrega (formato YYYY-MM-DD, geralmente igual à data_entrega)
- pecas: Lista de objetos, cada um contendo:
  - nome_peca: Nome da peça
  - quantidade: Quantidade (inteiro)
  - preco_unitario: Preço unitário (número decimal)

Se alguma informação não estiver disponível, use valores padrão razoáveis baseados no contexto.

**Texto do PDF:**
{pdf_text}

**IMPORTANTE:** Retorne APENAS o JSON válido, sem markdown, sem explicações, apenas o objeto JSON puro."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um assistente que extrai dados estruturados de documentos e retorna apenas JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        
        data = json.loads(result)
        return data
        
    except Exception as e:
        print(f"Erro ao processar com IA: {e}")
        return None

def extract_data_from_message(message, current_data, history=[]):
    """
    Uses OpenAI to extract order data, search intents, delete intents, and update intents from the message.
    'history' is a list of recent messages to provide context.
    """
    
    # Format history for the prompt
    history_str = ""
    if history:
        history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])
    else:
        history_str = "Nenhum histórico recente."

    prompt = f"""
Você é um assistente especializado em extrair dados de pedidos de produção.
Analise a mensagem do usuário e o contexto atual.

**Dados Atuais (Contexto):**
{current_data}

**Mensagem do Usuário:**
{message}

**Regras de Extração:**
- Se o usuário disser "hoje" para datas, use {date.today()}.
- Para 'icms', se não informado, assuma 0.
- Para 'previsao_entrega', se não informado, assuma igual à 'data_entrega'.
- Mantenha os dados do contexto a menos que o usuário os altere explicitamente.
- **Para DELETAR:** Se o usuário quiser remover/excluir/deletar algo.
  - 'delete_target': "order" ou "part".
  - 'delete_query': O termo identificador.

- **Para EDITAR/ATUALIZAR:** Se o usuário quiser mudar/alterar/corrigir algo.
  - 'update_target': "order" ou "part".
  - 'update_query': O termo identificador (ex: código OP, nome peça).
  - 'update_fields': Objeto JSON com os campos a alterar e novos valores.
    - Se o usuário disser "mudar o cliente" mas não disser o nome, NÃO invente. Deixe o valor como null.
  - 'missing_update_value': Nome do campo que o usuário quer mudar mas não informou o valor (ex: "nome_cliente").
  - 'missing_update_question': Pergunta natural pedindo o novo valor (ex: "Para qual cliente você quer mudar?").

**Histórico da Conversa:**
{history_str}

**Saída JSON:**
Retorne APENAS um JSON com a seguinte estrutura:
{{
  "is_order_intent": boolean, 
  "is_search_intent": boolean,
  "is_delete_intent": boolean,
  "is_update_intent": boolean,
  "search_query": "string ou null",
  "delete_target": "string ou null",
  "delete_query": "string ou null",
  "update_target": "string ou null",
  "update_query": "string ou null",
  "update_fields": {{ ... campos a alterar ... }},
  "missing_update_value": "string ou null",
  "missing_update_question": "string ou null",
  "data": {{ ... objeto com todos os campos acumulados ... }},
  "missing_fields": [ ... lista de strings com os nomes dos campos OBRIGATÓRIOS que faltam ... ],
  "missing_message": "Pergunta curta pedindo os dados obrigatórios que faltam. Null se não faltar nada."
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um assistente de API que retorna apenas JSON estrito."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        
        return json.loads(result)
        
    except Exception as e:
        return None

def extract_parts_from_message(user_message):
    """Extract just parts list from message"""
    prompt = f"""Extraia uma lista de peças de produção do texto abaixo.
    
Texto: {user_message}
    
Retorne JSON:
{{
  "pecas": [
    {{ "nome_peca": "string", "quantidade": int, "preco_unitario": float }}
  ]
}}
Se não encontrar peças, retorne lista vazia.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        result = response.choices[0].message.content.strip()
        if result.startswith("```"): result = result.split("```")[1]
        if result.startswith("json"): result = result[4:]
        return json.loads(result).get("pecas", [])
    except:
        return []

def fetch_alerts():
    """Fetch alerts from API"""
    try:
        res = requests.post(f"{API_URL}/analyze")
        if res.status_code == 200:
            return res.json()
        return None
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def create_order(order_data):
    """Create order in API"""
    try:
        res = requests.post(f"{API_URL}/orders", json=order_data)
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        # Return a dummy response object so the UI can show the error
        class ErrorResponse:
            status_code = 500
            text = str(e)
            def json(self): return {"detail": str(e)}
        return ErrorResponse()

def create_parts(parts_data):
    """Create parts in API"""
    try:
        res = requests.post(f"{API_URL}/parts", json=parts_data)
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def search_parts(query=None):
    """Search parts by name, client, OP or status"""
    try:
        params = {"query": query} if query else {}
        res = requests.get(f"{API_URL}/parts/search", params=params)
        if res.status_code == 200:
            return res.json()
        return []
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return []

def search_orders(query=None):
    """Search orders by client or OP"""
    try:
        params = {"query": query} if query else {}
        res = requests.get(f"{API_URL}/orders", params=params)
        if res.status_code == 200:
            return res.json()
        return []
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return []

def get_order(codigo_op):
    """Get order details"""
    try:
        res = requests.get(f"{API_URL}/orders/{codigo_op}")
        if res.status_code == 200:
            return res.json()
        return None
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def update_order(codigo_op, data):
    """Update order details"""
    try:
        res = requests.put(f"{API_URL}/orders/{codigo_op}", json=data)
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def delete_order(codigo_op):
    """Delete order"""
    try:
        res = requests.delete(f"{API_URL}/orders/{codigo_op}")
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def get_order_parts(codigo_op):
    """Get parts for an order"""
    try:
        res = requests.get(f"{API_URL}/orders/{codigo_op}/parts")
        if res.status_code == 200:
            return res.json()
        return []
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return []

def update_part(part_id, data):
    """Update part details"""
    try:
        res = requests.put(f"{API_URL}/parts/{part_id}", json=data)
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def delete_part(part_id):
    """Delete part"""
    try:
        res = requests.delete(f"{API_URL}/parts/{part_id}")
        return res
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

