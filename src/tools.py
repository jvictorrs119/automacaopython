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

def get_openai_client():
    if not OPENAI_API_KEY:
        print("Warning: OPENAI_API_KEY not found.")
        return None
    return OpenAI(api_key=OPENAI_API_KEY)

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
        client = get_openai_client()
        if not client: return None
        
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
{json.dumps(current_data, ensure_ascii=False) if current_data else "Nenhum processo em andamento."}

**Mensagem do Usuário:**
"{message}"

**Regras de Prioridade (Contexto):**
1. **CONTINUIDADE:** Se houver 'Dados Atuais' com campos faltando (ex: criando pedido e falta 'nome_cliente'), e o usuário responder algo curto (ex: "João Pedro", "Coca Cola"), ASSUMA que ele está fornecendo o dado que falta. **NÃO** classifique como busca.
2. **EXTRAÇÃO DE CLIENTE:**
   - "crie uma op para [CLIENTE]" -> Extraia [CLIENTE] como 'nome_cliente'.
   - "pedido do [CLIENTE]" -> Extraia [CLIENTE] como 'nome_cliente'.
   - "op da [CLIENTE]" -> Extraia [CLIENTE] como 'nome_cliente'.
   - Se o nome for composto (ex: "Joao Pedro"), extraia o nome completo.

**Regras Gerais:**
- Se o usuário disser "hoje" para datas, use {date.today()}.
- Para 'icms', se não informado, assuma 0.
- Para 'previsao_entrega', se não informado, assuma igual à 'data_entrega'.
- **Para DELETAR:** Se o usuário quiser remover/excluir/deletar algo.
  - 'delete_target': "order" ou "part".
  - 'delete_query': O termo identificador.

- **Para EDITAR/ATUALIZAR:** Se o usuário quiser mudar/alterar/corrigir algo.
  - 'update_target': "order" ou "part".
  - 'update_query': O termo identificador.
  - 'update_fields': Objeto JSON com os campos a alterar.

**Histórico Recente:**
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
  "update_fields": {{ ... }},
  "data": {{ ... objeto com todos os campos acumulados (mescle os dados novos com os do contexto) ... }},
  "missing_fields": [ ... lista de strings com os nomes dos campos OBRIGATÓRIOS que AINDA faltam ... ],
  "missing_message": "Pergunta curta pedindo os dados obrigatórios que faltam. Null se não faltar nada."
}}
"""

    try:
        client = get_openai_client()
        if not client: return None

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
        client = get_openai_client()
        if not client: return []

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

def generate_agent_response(user_message, action_result, context_data=None):
    """
    Generates a natural language response for the user based on the action result.
    This ensures the agent follows the persona and instructions.
    """
    
    prompt = f"""
    Você é um assistente de produção industrial inteligente e prestativo.
    Seu objetivo é ajudar o usuário a gerenciar pedidos e peças.
    
    **Mensagem do Usuário:** "{user_message}"
    
    **Resultado da Ação (Sistema):**
    {json.dumps(action_result, ensure_ascii=False, indent=2)}
    
    **Contexto Atual:**
    {json.dumps(context_data, ensure_ascii=False, indent=2) if context_data else "Nenhum"}
    
    **Instruções:**
    1. Responda de forma natural, amigável e profissional.
    2. Use emojis para tornar a mensagem visualmente agradável (🏭, ✅, ⚠️, 📦, etc).
    3. Se o resultado for uma lista de itens (busca), formate-os de forma clara (ex: bullet points).
    4. Se o sistema pedir confirmação (ex: "awaiting_confirmation"), pergunte ao usuário claramente.
    5. Se houve erro, explique de forma simples.
    6. NÃO invente dados que não estão no resultado.
    
    Gere APENAS o texto da resposta.
    """
    
    try:
        client = get_openai_client()
        if not client: return "Desculpe, serviço de IA indisponível."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Desculpe, não consegui gerar uma resposta agora."

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

