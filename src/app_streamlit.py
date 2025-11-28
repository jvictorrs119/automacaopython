import streamlit as st
import os
from dotenv import load_dotenv
from agent import ProductionAgent
from tools import fetch_alerts

load_dotenv()

st.set_page_config(page_title="Monitoramento de Produção", page_icon="🏭")

st.title("🏭 Assistente de Produção")

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Olá! Sou seu assistente de produção. 📎 Anexe um PDF de pedido e me envie uma mensagem para processá-lo, ou use os botões na barra lateral."
    })

if "agent" not in st.session_state:
    st.session_state.agent = ProductionAgent()

if "chat_context" not in st.session_state:
    st.session_state.chat_context = []

def update_chat_context(role, content):
    """Update chat history keeping only last 10 messages"""
    st.session_state.chat_context.append({"role": role, "content": content})
    if len(st.session_state.chat_context) > 10:
        st.session_state.chat_context.pop(0)

# Sidebar for actions
with st.sidebar:
    st.header("Ações")
    
    if st.button("Verificar Alertas 🚨"):
        data = fetch_alerts()
        if data:
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
            st.error("Erro ao verificar alertas.")

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
        # Prepare input
        prompt = user_input
        
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        update_chat_context("user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with Agent
        with st.chat_message("assistant"):
            with st.spinner("🤖 Processando..."):
                # Pass chat context to agent so it knows history
                response_obj = st.session_state.agent.process_input(
                    user_message=user_input, # Pass raw text input
                    attached_file=None,
                    chat_history=st.session_state.chat_context
                )
                
                response_text = response_obj.get("response", "Sem resposta.")
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                update_chat_context("assistant", response_text)
        
        st.rerun()
