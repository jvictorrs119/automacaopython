import streamlit as st
import os
from dotenv import load_dotenv
from tools import (
    extract_text_from_pdf, 
    extract_data_with_ai, 
    extract_data_from_message, 
    extract_parts_from_message,
    fetch_alerts,
    create_order,
    create_parts,
    search_orders,
    search_parts,
    get_order_parts,
    delete_order,
    delete_part,
    update_order,
    update_part
)

load_dotenv()

st.set_page_config(page_title="Monitoramento de Produção", page_icon="🏭")

st.title("🏭 Assistente de Produção")

if "chat_context" not in st.session_state:
    st.session_state.chat_context = []

def update_chat_context(role, content):
    """Update chat history keeping only last 10 messages"""
    st.session_state.chat_context.append({"role": role, "content": content})
    if len(st.session_state.chat_context) > 10:
        st.session_state.chat_context.pop(0)

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Olá! Sou seu assistente de produção. 📎 Anexe um PDF de pedido e me envie uma mensagem para processá-lo, ou use os botões na barra lateral."
    })

if "attached_file" not in st.session_state:
    st.session_state.attached_file = None

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
    c1, c2, c3 = st.columns([1, 8, 1])
    with c1:
        new_file = st.file_uploader("📎", type="pdf", label_visibility="collapsed")
    with c2:
        user_input = st.text_input("Mensagem", placeholder="Digite sua mensagem...", label_visibility="collapsed")
    with c3:
        submit_clicked = st.form_submit_button("Enviar")

# Show attachment indicator if file is attached (from previous state or just uploaded)
if st.session_state.get("attached_file") and not submit_clicked:
     st.info(f"📎 Arquivo em memória: {st.session_state.attached_file_name}")

if submit_clicked:
    if not user_input and not new_file:
        st.warning("⚠️ Digite uma mensagem ou anexe um arquivo.")
    else:
        # Update attached file if a new one is uploaded
        if new_file:
            st.session_state.attached_file = new_file
            st.session_state.attached_file_name = new_file.name
            # Reset processing flags for new file
            if "pdf_processed" in st.session_state: del st.session_state.pdf_processed
            if "extracted_data" in st.session_state: del st.session_state.extracted_data
        
        prompt = user_input if user_input else ""
        
        # Display and save user message
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            update_chat_context("user", prompt)
            with st.chat_message("user"):
                st.markdown(prompt)
        elif new_file:
            msg_content = f"📎 Enviou arquivo: {new_file.name}"
            st.session_state.messages.append({"role": "user", "content": msg_content})
            update_chat_context("user", msg_content)
            with st.chat_message("user"):
                st.markdown(msg_content)

        # --- Logic for processing ---
        
        # Check if there's an attached PDF to process
        if st.session_state.get("attached_file") and "pdf_processed" not in st.session_state:
            with st.chat_message("assistant"):
                with st.spinner("🤖 Processando PDF com IA..."):
                    # Extract text from PDF
                    pdf_text = extract_text_from_pdf(st.session_state.attached_file)
                    
                    # Use AI to extract data
                    data = extract_data_with_ai(pdf_text)
                    
                    if data:
                        st.session_state.extracted_data = data
                        st.session_state.pdf_processed = True
                        
                        msg = f"""📄 **Analisei o arquivo {st.session_state.attached_file_name}**

**Dados extraídos:**
- 👤 Cliente: {data.get('nome_cliente')}
- 📋 Pedido nº: {data.get('numero_pedido')}
- 📅 Data do Pedido: {data.get('data_pedido')}
- 🚚 Data de Entrega: {data.get('data_entrega')}
- 💰 Valor Total: R$ {data.get('preco_total', 0):.2f}
- 📦 Itens: {len(data.get('pecas', []))} peça(s)

Deseja criar a Ordem de Produção com estes dados?"""
                        
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.markdown(msg)
                        # Clear attachment after processing
                        st.session_state.attached_file = None
                        st.session_state.attached_file_name = None
                        st.rerun()
                    else:
                        msg = "❌ Não consegui extrair os dados do PDF. Verifique o formato do arquivo."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.markdown(msg)
                        st.rerun()
        
        # Logic for conversation flow (confirmations)
        elif "extracted_data" in st.session_state and st.session_state.get("pdf_processed"):
            p_lower = prompt.lower()
            if any(k in p_lower for k in ["sim", "s", "yes", "ok", "pode", "cri", "confirm"]):
                # Call API to create order
                data = st.session_state.extracted_data
                order_payload = {k: v for k, v in data.items() if k != "pecas"}
                
                with st.spinner("Criando ordem..."):
                    res_order = create_order(order_payload)
                    
                if res_order and res_order.status_code == 200:
                    op_code = res_order.json()["codigo_op"]
                    st.session_state.current_op = op_code
                    
                    # Check if we have parts to register
                    pending_parts = data.get("pecas", [])
                    
                    if pending_parts:
                        with st.chat_message("assistant"):
                            msg = f"✅ **Ordem (OP) criada! Código: `{op_code}`**\n\nIdentifiquei {len(pending_parts)} peças. Deseja cadastrá-las agora?"
                            st.markdown(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.session_state.awaiting_parts_confirmation = True
                        st.session_state.pending_parts = pending_parts
                    else:
                        with st.chat_message("assistant"):
                            msg = f"✅ **Ordem (OP) criada! Código: `{op_code}`**\n\nDeseja adicionar peças a esta OP agora?"
                            st.markdown(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.session_state.awaiting_parts_input = True
                    
                    del st.session_state.extracted_data
                    del st.session_state.pdf_processed
                    st.rerun()
                    
                else:
                    err = res_order.text if res_order else "Erro desconhecido"
                    st.error(f"Erro ao criar ordem: {err}")
                    
            elif any(k in p_lower for k in ["não", "nao", "no", "cancel"]):
                with st.chat_message("assistant"):
                    msg = "Operação cancelada."
                    st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                if "extracted_data" in st.session_state:
                    del st.session_state.extracted_data
                if "pdf_processed" in st.session_state:
                    del st.session_state.pdf_processed
                st.rerun()
            else:
                # Try to interpret as a correction/update to the current data
                with st.spinner("🔄 Verificando alteração..."):
                    current_data = st.session_state.extracted_data
                    update_result = extract_data_from_message(prompt, current_data, st.session_state.chat_context)
                
                # Check if it looks like a valid update (has data and is order intent)
                if update_result and update_result.get("is_order_intent"):
                    # Update the data
                    new_data = update_result.get("data")
                    st.session_state.extracted_data = new_data
                    
                    msg = f"""🔄 **Dados Atualizados!**

**Dados identificados:**
- 👤 Cliente: {new_data.get('nome_cliente')}
- 📋 Pedido nº: {new_data.get('numero_pedido')}
- 📅 Data do Pedido: {new_data.get('data_pedido')}
- 🚚 Data de Entrega: {new_data.get('data_entrega')}
- 💰 Valor Total: R$ {new_data.get('preco_total', 0):.2f}
- 📦 Itens: {len(new_data.get('pecas', []))} peça(s)

Deseja criar a Ordem de Produção com estes dados?"""
                    
                    with st.chat_message("assistant"):
                        st.markdown(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.rerun()
                else:
                    with st.chat_message("assistant"):
                        msg = "🤔 Não entendi. Responda com **'Sim'** para criar a ordem, **'Não'** para cancelar, ou digite a correção (ex: 'O valor é 500')."
                        st.markdown(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.rerun()

        elif st.session_state.get("awaiting_parts_confirmation"):
            p_lower = prompt.lower()
            if any(k in p_lower for k in ["sim", "s", "yes", "ok", "cri", "pode", "confirm"]):
                # Create parts
                if "pending_parts" in st.session_state and "current_op" in st.session_state:
                    parts_payload = {
                        "codigo_op": st.session_state.current_op,
                        "pecas": st.session_state.pending_parts
                    }
                    
                    with st.spinner("Cadastrando peças..."):
                        res_parts = create_parts(parts_payload)
                        
                    if res_parts and res_parts.status_code == 200:
                        with st.chat_message("assistant"):
                            msg = f"✅ **Peças cadastradas com sucesso!**\n\nO sistema agora está monitorando esta produção."
                            st.markdown(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        err = res_parts.text if res_parts else "Erro desconhecido"
                        st.error(f"Erro ao criar peças: {err}")
                    
                    # Cleanup
                    del st.session_state.awaiting_parts_confirmation
                    del st.session_state.pending_parts
                    del st.session_state.current_op
                    st.rerun()
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "⚠️ Erro de estado: Dados perdidos."})
                    st.rerun()
            elif any(k in p_lower for k in ["não", "nao", "no", "cancel"]):
                with st.chat_message("assistant"):
                    msg = "Ok, peças não cadastradas. A OP continua ativa."
                    st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                del st.session_state.awaiting_parts_confirmation
                if "pending_parts" in st.session_state: del st.session_state.pending_parts
                if "current_op" in st.session_state: del st.session_state.current_op
                st.rerun()
            else:
                with st.chat_message("assistant"):
                    msg = "Responda 'Sim' para confirmar as peças ou 'Não' para pular."
                    st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()

        elif st.session_state.get("awaiting_parts_input"):
            p_lower = prompt.lower()
            if any(k in p_lower for k in ["não", "nao", "no", "cancel"]):
                with st.chat_message("assistant"):
                    msg = "Ok, finalizado sem cadastrar peças."
                    st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                del st.session_state.awaiting_parts_input
                if "current_op" in st.session_state: del st.session_state.current_op
                st.rerun()
            else:
                # User might have sent "Sim" or directly the parts
                if p_lower in ["sim", "s", "yes"]:
                    msg = "Por favor, digite as peças (Nome, Quantidade, Preço)."
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.rerun()
                else:
                    # Try to extract parts
                    with st.spinner("Lendo peças..."):
                        parts = extract_parts_from_message(prompt)
                    
                    if parts:
                        st.session_state.pending_parts = parts
                        st.session_state.awaiting_parts_confirmation = True
                        del st.session_state.awaiting_parts_input
                        
                        msg = f"Identifiquei {len(parts)} peças. Confirma o cadastro?"
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                    else:
                        msg = "Não identifiquei as peças. Tente listar como: 'Nome - Qtd - Preço'."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()

        elif st.session_state.get("awaiting_delete_confirmation"):
            p_lower = prompt.lower()
            if any(k in p_lower for k in ["sim", "s", "yes", "ok", "confirm"]):
                candidate = st.session_state.get("delete_candidate")
                if candidate:
                    with st.spinner("Deletando..."):
                        if candidate["type"] == "order":
                            res = delete_order(candidate["data"]["codigo_op"])
                        else:
                            res = delete_part(candidate["data"]["id_peca"])
                            
                    if res and res.status_code == 200:
                        msg = "✅ Item deletado com sucesso!"
                    else:
                        msg = "❌ Erro ao deletar item."
                        
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    del st.session_state.awaiting_delete_confirmation
                    del st.session_state.delete_candidate
                    st.rerun()
                else:
                    st.error("Erro de estado: Candidato perdido.")
                    del st.session_state.awaiting_delete_confirmation
                    st.rerun()
                    
            elif any(k in p_lower for k in ["não", "nao", "no", "cancel"]):
                msg = "Operação cancelada."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                del st.session_state.awaiting_delete_confirmation
                del st.session_state.delete_candidate
                st.rerun()
            else:
                msg = "Responda 'Sim' para confirmar a exclusão ou 'Não' para cancelar."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()

        elif st.session_state.get("awaiting_update_confirmation"):
            p_lower = prompt.lower()
            if any(k in p_lower for k in ["sim", "s", "yes", "ok", "confirm"]):
                candidate = st.session_state.get("update_candidate")
                if candidate:
                    with st.spinner("Atualizando..."):
                        if candidate["type"] == "order":
                            res = update_order(candidate["data"]["codigo_op"], candidate["fields"])
                        else:
                            res = update_part(candidate["data"]["id_peca"], candidate["fields"])
                            
                    if res and res.status_code == 200:
                        msg = "✅ Item atualizado com sucesso!"
                    else:
                        msg = "❌ Erro ao atualizar item."
                        
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    del st.session_state.awaiting_update_confirmation
                    del st.session_state.update_candidate
                    st.rerun()
                else:
                    st.error("Erro de estado: Candidato perdido.")
                    del st.session_state.awaiting_update_confirmation
                    st.rerun()
                    
            elif any(k in p_lower for k in ["não", "nao", "no", "cancel"]):
                msg = "Operação cancelada."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                del st.session_state.awaiting_update_confirmation
                del st.session_state.update_candidate
                st.rerun()
            else:
                msg = "Responda 'Sim' para confirmar a alteração ou 'Não' para cancelar."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()

        elif "partial_update" in st.session_state:
            # User provided the missing value
            partial = st.session_state.partial_update
            new_value = prompt
            
            # Construct the update fields
            fields = {partial["field"]: new_value}
            target = partial["target"]
            query = partial["query"]
            
            # Proceed to search and confirm (reuse logic by setting update intent manually or just copying logic)
            # Let's copy the search/confirm logic here for simplicity
            
            with st.spinner(f"✏️ Buscando '{query}' para edição..."):
                candidates_orders = []
                candidates_parts = []
                if target in ["order", "any"]:
                    candidates_orders = search_orders(query)
                if target in ["part", "any"]:
                    candidates_parts = search_parts(query)
            
            total_found = len(candidates_orders) + len(candidates_parts)
            
            if total_found == 1:
                if candidates_orders:
                    item = candidates_orders[0]
                    st.session_state.update_candidate = {"type": "order", "data": item, "fields": fields}
                    msg = f"⚠️ **Confirmar alteração?**\n\n**Pedido:** {item['codigo_op']} | **Cliente:** {item['nome_cliente']}\n\n**Novos valores:** {partial['field']}: {new_value}"
                else:
                    item = candidates_parts[0]
                    st.session_state.update_candidate = {"type": "part", "data": item, "fields": fields}
                    msg = f"⚠️ **Confirmar alteração?**\n\n**Peça:** {item['nome_peca']} | **OP:** {item['codigo_op']}\n\n**Novos valores:** {partial['field']}: {new_value}"
                
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.session_state.awaiting_update_confirmation = True
                del st.session_state.partial_update
                st.rerun()
            elif total_found == 0:
                msg = f"❌ Não encontrei nada com '{query}'."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                del st.session_state.partial_update
                st.rerun()
            else:
                 msg = f"⚠️ Encontrei {total_found} itens. Seja mais específico."
                 st.session_state.messages.append({"role": "assistant", "content": msg})
                 del st.session_state.partial_update
                 st.rerun()

        else:
            # Default response - treat as general question OR try to parse as order
            if prompt: 
                # Check for cancellation
                if any(k in prompt.lower() for k in ["cancelar", "cancel", "pare", "stop"]):
                    if "partial_order" in st.session_state:
                        del st.session_state.partial_order
                        msg = "❌ Criação de pedido cancelada."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                
                # Try to extract/update order data
                with st.spinner("🤔 Analisando..."):
                    current_context = st.session_state.get("partial_order", None)
                    extraction_result = extract_data_from_message(prompt, current_context, st.session_state.chat_context)
                
                if extraction_result and extraction_result.get("is_order_intent"):
                    data = extraction_result.get("data")
                    missing = extraction_result.get("missing_fields", [])
                    
                    if not missing:
                        # All data is present!
                        st.session_state.extracted_data = data
                        st.session_state.pdf_processed = True
                        # Clear partial state
                        if "partial_order" in st.session_state:
                            del st.session_state.partial_order
                        
                        msg = f"""📝 **Pedido Completo!**
                    
**Dados identificados:**
- 👤 Cliente: {data.get('nome_cliente')}
- 📋 Pedido nº: {data.get('numero_pedido')}
- 📅 Data do Pedido: {data.get('data_pedido')}
- 🚚 Data de Entrega: {data.get('data_entrega')}
- 💰 Valor Total: R$ {data.get('preco_total', 0):.2f}
- 📦 Itens: {len(data.get('pecas', []))} peça(s)

Deseja criar a Ordem de Produção com estes dados?"""
                        
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                    else:
                        # Missing data - ask user
                        st.session_state.partial_order = data
                        question = extraction_result.get("missing_message") or f"Faltam os seguintes dados: {', '.join(missing)}. Poderia informar?"
                        st.session_state.messages.append({"role": "assistant", "content": question})
                        st.rerun()
                
                elif extraction_result and extraction_result.get("is_search_intent"):
                    query = extraction_result.get("search_query")
                    with st.spinner(f"🔎 Buscando por '{query}'..."):
                        # 1. Search Orders
                        orders = search_orders(query)
                        
                        # 2. Search Parts
                        parts = search_parts(query)
                        
                        # 3. Organize data
                        # Create a map of OP -> Parts for the found orders
                        order_parts_map = {}
                        found_ops = set()
                        
                        if orders:
                            for o in orders:
                                op = o['codigo_op']
                                found_ops.add(op)
                                # Fetch parts for this order (to ensure we show them even if search didn't match parts directly)
                                p_list = get_order_parts(op)
                                order_parts_map[op] = p_list
                        
                        # Identify parts that matched the query but whose order wasn't found (orphaned search results)
                        standalone_parts = []
                        if parts:
                            for p in parts:
                                if p['codigo_op'] not in found_ops:
                                    standalone_parts.append(p)
                    
                    if orders or standalone_parts:
                        msg = f"✅ **Resultados para '{query}':**\n\n"
                        
                        if orders:
                            msg += "**📋 Pedidos Encontrados:**\n"
                            for o in orders:
                                op = o['codigo_op']
                                msg += f"**🔹 OP:** `{op}` | **Cliente:** {o['nome_cliente']} | **Status:** {o['status']}\n"
                                
                                # List parts for this order
                                p_list = order_parts_map.get(op, [])
                                if p_list:
                                    for p in p_list:
                                        msg += f"&nbsp;&nbsp;&nbsp;&nbsp;📦 {p['nome_peca']} | Qtd: {p['pecas_produzidas']}/{p['quantidade']} | {p['status']}\n"
                                else:
                                    msg += "&nbsp;&nbsp;&nbsp;&nbsp;*Sem peças cadastradas*\n"
                                msg += "\n"
                            
                        if standalone_parts:
                            msg += "**📦 Outras Peças Encontradas:**\n"
                            for p in standalone_parts:
                                msg += f"- **Peça:** {p['nome_peca']} | **OP:** `{p['codigo_op']}` | **Status:** {p['status']}\n"
                    else:
                        msg = f"❌ Nenhum resultado encontrado para '{query}'."
                        
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.rerun()
                
                elif extraction_result and extraction_result.get("is_delete_intent"):
                    target = extraction_result.get("delete_target")
                    query = extraction_result.get("delete_query")
                    
                    with st.spinner(f"🗑️ Buscando '{query}' para exclusão..."):
                        # Search for candidates
                        candidates_orders = []
                        candidates_parts = []
                        
                        if target in ["order", "any"]:
                            candidates_orders = search_orders(query)
                        if target in ["part", "any"]:
                            candidates_parts = search_parts(query)
                            
                    total_found = len(candidates_orders) + len(candidates_parts)
                    
                    if total_found == 0:
                        msg = f"❌ Não encontrei nada com '{query}' para deletar."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                        
                    elif total_found == 1:
                        # Found exactly one item - ask for confirmation
                        if candidates_orders:
                            item = candidates_orders[0]
                            st.session_state.delete_candidate = {"type": "order", "data": item}
                            msg = f"⚠️ **Confirmar exclusão?**\n\n**Pedido:** {item['codigo_op']} | **Cliente:** {item['nome_cliente']}\n\n*Isso apagará o pedido e todas as suas peças.*"
                        else:
                            item = candidates_parts[0]
                            st.session_state.delete_candidate = {"type": "part", "data": item}
                            msg = f"⚠️ **Confirmar exclusão?**\n\n**Peça:** {item['nome_peca']} | **OP:** {item['codigo_op']} | **Qtd:** {item['quantidade']}"
                            
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.session_state.awaiting_delete_confirmation = True
                        st.rerun()
                        
                    else:
                        # Multiple items found
                        msg = f"⚠️ **Encontrei {total_found} itens. Qual deles você quer deletar?**\n\n"
                        
                        for o in candidates_orders:
                            msg += f"- **Pedido:** `{o['codigo_op']}` ({o['nome_cliente']})\n"
                        for p in candidates_parts:
                            msg += f"- **Peça:** {p['nome_peca']} (OP: `{p['codigo_op']}`)\n"
                            
                        msg += "\nPor favor, seja mais específico (ex: 'deletar pedido X' ou 'deletar peça Y')."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()

                elif extraction_result and extraction_result.get("is_update_intent"):
                    target = extraction_result.get("update_target")
                    query = extraction_result.get("update_query")
                    fields = extraction_result.get("update_fields", {})
                    missing_val = extraction_result.get("missing_update_value")
                    missing_question = extraction_result.get("missing_update_question")
                    
                    if missing_val:
                        # Ask for the missing value
                        st.session_state.partial_update = {
                            "target": target,
                            "query": query,
                            "field": missing_val
                        }
                        # Use the natural question from AI if available, otherwise fallback
                        msg = missing_question if missing_question else f"Para qual valor você deseja alterar o campo **{missing_val}** de '{query}'?"
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                    
                    with st.spinner(f"✏️ Buscando '{query}' para edição..."):
                        # Search for candidates
                        candidates_orders = []
                        candidates_parts = []
                        
                        if target in ["order", "any"]:
                            candidates_orders = search_orders(query)
                        if target in ["part", "any"]:
                            candidates_parts = search_parts(query)
                            
                    total_found = len(candidates_orders) + len(candidates_parts)
                    
                    if total_found == 0:
                        msg = f"❌ Não encontrei nada com '{query}' para editar."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                        
                    elif total_found == 1:
                        # Found exactly one item - ask for confirmation
                        if candidates_orders:
                            item = candidates_orders[0]
                            st.session_state.update_candidate = {"type": "order", "data": item, "fields": fields}
                            changes_str = ", ".join([f"{k}: {v}" for k, v in fields.items()])
                            msg = f"⚠️ **Confirmar alteração?**\n\n**Pedido:** {item['codigo_op']} | **Cliente:** {item['nome_cliente']}\n\n**Novos valores:** {changes_str}"
                        else:
                            item = candidates_parts[0]
                            st.session_state.update_candidate = {"type": "part", "data": item, "fields": fields}
                            changes_str = ", ".join([f"{k}: {v}" for k, v in fields.items()])
                            msg = f"⚠️ **Confirmar alteração?**\n\n**Peça:** {item['nome_peca']} | **OP:** {item['codigo_op']}\n\n**Novos valores:** {changes_str}"
                            
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.session_state.awaiting_update_confirmation = True
                        st.rerun()
                        
                    else:
                        # Multiple items found
                        msg = f"⚠️ **Encontrei {total_found} itens. Qual deles você quer editar?**\n\n"
                        for o in candidates_orders:
                            msg += f"- **Pedido:** `{o['codigo_op']}` ({o['nome_cliente']})\n"
                        for p in candidates_parts:
                            msg += f"- **Peça:** {p['nome_peca']} (OP: `{p['codigo_op']}`)\n"
                        msg += "\nSeja mais específico (ex: 'editar pedido X' ou 'editar peça Y')."
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()

                else:
                    # Not an order intent
                    if "partial_order" in st.session_state:
                        # If we were in the middle of an order but user said something unrelated, 
                        # we can either ignore or ask if they want to cancel. 
                        # For now, let's assume they might be confused and remind them of the order.
                        msg = "Não entendi. Estamos criando um pedido. " + (st.session_state.get("partial_order_question") or "Por favor, informe os dados faltantes ou digite 'cancelar'.")
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
                    else:
                        # Generic response
                        with st.chat_message("assistant"):
                            msg = "Para processar um pedido, anexe um PDF usando o botão 📎 ou envie uma mensagem com os dados (Cliente, Nº Pedido, Datas, Peças, etc)."
                            st.markdown(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()
