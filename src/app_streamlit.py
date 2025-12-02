import streamlit as st
import os
import requests
import uuid
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Monitoramento de Produção", page_icon="🏭")

st.title("🏭 Assistente de Produção")

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Olá! Sou seu assistente de produção. Posso ajudar a criar pedidos, cadastrar peças e verificar alertas."
    })

# Sidebar for actions
with st.sidebar:
    st.header("Ações")
    st.caption(f"Sessão: {st.session_state.session_id}")
    
    if st.button("Verificar Alertas 🚨"):
        try:
            res = requests.post(f"{API_URL}/analyze")
            if res.status_code == 200:
                data = res.json()
                alerts = data.get("alerts", [])
                st.session_state.messages.append({"role": "user", "content": "Verificar alertas de produção."})
                
                if alerts:
                    msg = f"⚠️ **Encontrei {len(alerts)} alertas de atraso/risco:**\n\n"
                    for a in alerts:
                        msg += f"- **OP:** {a['codigo_op']} | **Peça:** {a['peca']} | **Motivo:** {a['motivo']}\n"
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "✅ Nenhum alerta encontrado. Produção dentro do prazo!"})
                st.rerun()
            else:
                st.error("Erro ao verificar alertas na API.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")

# Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

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
                    else:
                        response_text = f"Erro na API: {response.status_code} - {response.text}"
                    
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    
                except Exception as e:
                    err_msg = f"Erro de conexão com a API: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
        
        st.rerun()
