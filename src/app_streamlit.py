import streamlit as st
import os
import requests
import uuid
import tiktoken
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Initialize tiktoken encoder for GPT-4
try:
    encoding = tiktoken.encoding_for_model("gpt-4")
except:
    encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    if not text:
        return 0
    return len(encoding.encode(text))

st.set_page_config(page_title="Monitoramento de Produção", page_icon="🏭")

st.title("🏭 Assistente de Produção")

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Olá! Sou seu assistente de produção. Posso ajudar a criar pedidos, cadastrar peças e verificar alertas.",
        "tokens": 0
    })

# Token counters
if "total_input_tokens" not in st.session_state:
    st.session_state.total_input_tokens = 0
if "total_output_tokens" not in st.session_state:
    st.session_state.total_output_tokens = 0

# Sidebar for actions
with st.sidebar:
    st.header("Ações")
    st.caption(f"Sessão: {st.session_state.session_id}")
    
    # Token counter display
    st.divider()
    st.subheader("📊 Tokens OpenAI")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Msg User", st.session_state.total_input_tokens, help="Estimativa dos tokens nas mensagens do usuário")
    with col2:
        st.metric("API Total", st.session_state.total_output_tokens, help="Tokens reais gastos pela API (todas as chamadas LLM)")
    total = st.session_state.total_input_tokens + st.session_state.total_output_tokens
    st.info(f"**Total da Sessão:** {total} tokens")
    st.divider()
    
    if st.button("Verificar Alertas 🚨"):
        try:
            res = requests.post(f"{API_URL}/analyze")
            if res.status_code == 200:
                data = res.json()
                alerts = data.get("alerts", [])
                st.session_state.messages.append({"role": "user", "content": "Verificar alertas de produção.", "tokens": 0})
                
                if alerts:
                    msg = f"⚠️ **Encontrei {len(alerts)} alertas de atraso/risco:**\n\n"
                    for a in alerts:
                        msg += f"- **OP:** {a['codigo_op']} | **Peça:** {a['peca']} | **Motivo:** {a['motivo']}\n"
                    st.session_state.messages.append({"role": "assistant", "content": msg, "tokens": 0})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "✅ Nenhum alerta encontrado. Produção dentro do prazo!", "tokens": 0})
                st.rerun()
            else:
                st.error("Erro ao verificar alertas na API.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")
    
    if st.button("Limpar Contagem 🔄"):
        st.session_state.total_input_tokens = 0
        st.session_state.total_output_tokens = 0
        st.rerun()

# Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Show token count for each message
        tokens = message.get("tokens", 0)
        if tokens > 0:
            token_label = "🔵" if message["role"] == "user" else "🟢"
            st.caption(f"{token_label} {tokens} tokens")

# Input Area with Form
with st.form(key="chat_form", clear_on_submit=True):
    c1, c2 = st.columns([9, 1])
    with c1:
        user_input = st.text_input("Mensagem", placeholder="Digite sua mensagem...", label_visibility="collapsed")
    with c2:
        submit_clicked = st.form_submit_button("Enviar")

if submit_clicked:
    if not user_input:
        st.warning("⚠️ Digite uma mensagem.")
    else:
        # Count input tokens
        input_tokens = count_tokens(user_input)
        st.session_state.total_input_tokens += input_tokens
        
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input, "tokens": input_tokens})
        with st.chat_message("user"):
            st.markdown(user_input)
            st.caption(f"🔵 ~{input_tokens} tokens (msg)")

        # Process with API
        with st.chat_message("assistant"):
            with st.spinner("🤖 Processando..."):
                try:
                    payload = {
                        "message": user_input,
                        "phone_number": st.session_state.session_id, # Use session ID as identifier
                        "history": [] # API manages history now via Supabase
                    }
                    
                    response = requests.post(f"{API_URL}/chat", json=payload)
                    
                    if response.status_code == 200:
                        resp_data = response.json()
                        response_text = resp_data.get("response", "Sem resposta da API.")
                        # Get actual tokens used from API (includes all internal LLM calls)
                        api_tokens = resp_data.get("tokens_used", 0)
                    else:
                        response_text = f"Erro na API: {response.status_code} - {response.text}"
                        api_tokens = 0
                    
                    # Add API tokens to total
                    st.session_state.total_output_tokens += api_tokens
                    
                    st.markdown(response_text)
                    st.caption(f"🟢 {api_tokens} tokens (total API)")
                    st.session_state.messages.append({"role": "assistant", "content": response_text, "tokens": api_tokens})
                    
                except Exception as e:
                    err_msg = f"Erro de conexão com a API: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg, "tokens": 0})
        
        st.rerun()

