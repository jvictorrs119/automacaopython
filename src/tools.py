import os
import requests
import json
from datetime import date
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


def extract_data_from_message(message, current_data, history=[]):
    """
    Uses OpenAI to extract order data, search intents, delete intents, and update intents from the message.
    'history' is a list of recent messages to provide context.
    """
    
    # Format history for the prompt
    history_str = ""
    if history:
        if isinstance(history[0], dict):
            history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])
        else:
            # History is a list of strings "ROLE: Message"
            history_str = "\n".join(history)

    prompt = f"""
Você é um assistente especializado em extrair dados de pedidos de produção.
Analise a mensagem do usuário e o contexto atual para identificar a intenção e extrair dados.

**Dados Atuais (Contexto):**
{json.dumps(current_data, ensure_ascii=False) if current_data else "Nenhum processo em andamento."}

**Histórico Recente:**
{history_str}

**Mensagem do Usuário:**
"{message}"

**Regras de Prioridade (CRÍTICO):**
1. **CONTINUIDADE DE CONVERSA (Confirmations/Follow-ups):**
   - Se o usuário disser apenas "sim", "ok", "confirmo", "não", "cancelar":
     - Verifique o **Histórico Recente**. Se a última ação do assistente foi pedir confirmação para CRIAR PEDIDO, defina `is_order_intent` = true.
     - Se foi pedir confirmação para DELETAR, defina `is_delete_intent` = true.

2. **ADICIONAR PEÇAS (is_add_part_intent):**
   - Se o contexto tiver um `active_order_op` (ou se o usuário mencionar um número de pedido existente) e o usuário listar peças (nome, quantidade), isso é `is_add_part_intent`.
   - Exemplo: "Adicionar 10 peças X", "Peça Y: 5 unidades".

3. **CRIAR PEDIDO (is_order_intent):**
   - "crie uma op para [CLIENTE]" -> Extraia [CLIENTE] como 'nome_cliente'.
   - "pedido do [CLIENTE]" -> Extraia [CLIENTE] como 'nome_cliente'.
   - Se o usuário confirmar a criação de um pedido, mantenha `is_order_intent`.

**Campos Obrigatórios para CRIAR PEDIDO (is_order_intent = true):**
Para que o pedido seja considerado completo para CRIAÇÃO INICIAL, os seguintes dados são OBRIGATÓRIOS:
1. **nome_cliente**: String.
2. **numero_pedido**: Inteiro. (Se não informado, PERGUNTE).
3. **data_pedido**: Data (YYYY-MM-DD). (Se não informado, PERGUNTE).
4. **data_entrega**: Data (YYYY-MM-DD). (Se não informado, PERGUNTE).
5. **preco_total**: Float. (Se não informado, PERGUNTE).
6. **icms**: Float (Porcentagem ou valor). (Se não informado, PERGUNTE).

*Nota: As peças NÃO são obrigatórias nesta etapa. Elas serão pedidas DEPOIS.*

**Regras para ADICIONAR PEÇAS (is_add_part_intent = true):**
- Acionado quando o usuário quer cadastrar peças em um pedido.
- **Campos Obrigatórios:**
  1. **nome_peca**: String.
  2. **quantidade**: Inteiro.
  3. **nome_cliente**: String (Pode ser herdado do pedido se houver contexto).
  4. **codigo_op**: String (Se não houver um pedido recém-criado no contexto, o usuário DEVE informar).
- Se faltar algum dado, liste em `missing_fields`.

**Regras Gerais:**
- Para 'previsao_entrega', se não informado, assuma igual à 'data_entrega'.
- Para 'preco_total': Extraia apenas o número. Ex: "1500 reais" -> 1500.00.
- **Para DELETAR:** 'delete_target' ("order"/"part"), 'delete_query'.
- **Para EDITAR:** 'update_target', 'update_query', 'update_fields'.
- **Para BUSCAR (is_search_intent):**
  - O 'search_query' deve conter APENAS o termo essencial de busca.
  - Remova palavras como "cliente", "pedido", "op", "procure", "busque", "pesquise".
  - Exemplo: "procure cliente Yuri" -> search_query="Yuri"
  - Exemplo: "busque pedido 123" -> search_query="123"
  - Exemplo: "peça parafuso" -> search_query="parafuso"

**RESOLUÇÃO DE CONTEXTO (CRÍTICO):**
- Se o usuário disser "mude o valor", "qual o nome do cliente", "delete isso", ou qualquer referência a algo mencionado anteriormente:
  - OLHE O **Histórico Recente**.
  - Identifique sobre qual pedido ou peça o ASSISTENTE falou por último (ou listou em uma busca).
  - Se houve uma busca recente com vários resultados, e o usuário escolher um (ex: "edite o niple"), extraia "niple" como `update_query`.
  - Extraia o ID, Código OP ou Nome desse item do histórico e use como 'update_target'/'update_query' ou 'search_query'.
  - Exemplo: Histórico tem "Pedido 123 do João". Usuário diz "mude o valor para 500". -> is_update_intent=true, update_query="123", update_fields={{"preco_total": 500}}.

**Regras para ATUALIZAÇÃO (is_update_intent = true):**
- **PRÉ-REQUISITO:** O item a ser editado deve estar claro (pelo nome, ID, ou contexto recente).
- **CENÁRIO 1: Busca Necessária Primeiro**
  - Se o usuário disser "quero editar uma peça do cliente Yuri" (genérico) e NÃO houver peças desse cliente no histórico recente:
    - Defina `is_search_intent` = true.
    - `search_query` = "Yuri".
    - Motivo: Precisamos encontrar as peças antes de saber qual editar.
- **CENÁRIO 2: Edição Direta ou com Contexto**
  - Se o usuário disser "editar peça niple" (específico) OU se já houver uma lista de peças no contexto e ele disser "edite a peça niple":
    - Defina `is_update_intent` = true.
    - `update_target` = "part" (ou "order" se for pedido).
    - `update_query` = "niple".
    - Se houver `codigo_op` na frase, extraia também.
- **CENÁRIO 3: Valores da Edição**
  - Se o usuário der os novos valores (ex: "para 50"), coloque em `update_fields`.
  - Se NÃO der os valores, deixe `update_fields` vazio (o sistema perguntará).

**Saída JSON:**
Retorne APENAS um JSON com a seguinte estrutura:
{{
  "is_order_intent": boolean, 
  "is_add_part_intent": boolean,
  "is_search_intent": boolean,
  "is_delete_intent": boolean,
  "is_update_intent": boolean,
  "search_query": "string ou null",
  "delete_target": "string ou null",
  "delete_query": "string ou null",
  "update_target": "string ou null",
  "update_query": "string ou null",
  "codigo_op": "string ou null (OP para filtrar atualização/busca se citado)",
  "update_fields": {{ ... }},
  "target_op": "string ou null (OP alvo para adicionar peças, se citado)",
  "data": {{ ... objeto com todos os campos acumulados ... }},
  "parts_data": [ ... lista de objetos {{ "nome_peca":Str, "quantidade":Int, "nome_cliente":Str, "preco_unitario":Float }} ... ],
  "missing_fields": [ ... lista de strings com os nomes dos campos OBRIGATÓRIOS (nome_cliente, numero_pedido, data_pedido, data_entrega, preco_total, icms) que AINDA faltam ... ],
  "missing_message": "Pergunta curta e natural pedindo os dados que faltam. Null se não faltar nada."
}}
"""

    try:
        client = get_openai_client()
        if not client: return None

        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
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
            model="gpt-4.1-mini-2025-04-14",
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
    7. **CRÍTICO:** Se a ação foi "create_order" com sucesso, VOCÊ É OBRIGADO a perguntar se o usuário deseja cadastrar peças para esse pedido.
    8. **CRÍTICO:** Se o status for "confirmation_needed" (para criar pedido), NÃO pergunte sobre peças ainda. Pergunte APENAS se pode confirmar a criação do pedido.
    
    Gere APENAS o texto da resposta.
    """
    
    try:
        client = get_openai_client()
        if not client: return "Desculpe, serviço de IA indisponível."

        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
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


def get_chat_response(message, history=[]):
    """Generate a natural conversational response"""
    try:
        client = get_openai_client()
        if not client: return "Desculpe, serviço indisponível."

        # Format history
        history_str = ""
        if history:
            if isinstance(history[0], dict):
                history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-5:]])
            else:
                history_str = "\n".join(history[-5:])

        prompt = f"""
        Você é um assistente de produção industrial útil e amigável.
        O usuário enviou uma mensagem que NÃO é um comando específico de sistema (não é criar pedido, buscar, deletar, etc).
        
        Histórico:
        {history_str}
        
        Usuário: {message}
        
        Responda de forma prestativa, tirando dúvidas ou explicando o que você pode fazer (criar pedidos, buscar peças, verificar alertas).
        Seja breve.
        """

        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Desculpe, não consegui processar sua mensagem."
