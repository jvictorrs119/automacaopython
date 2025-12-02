import json
from tools import (
    extract_data_from_message, 
    extract_parts_from_message,
    get_chat_response,
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

class ProductionAgent:
    def __init__(self):
        # Internal state to track multi-turn conversations
        self.state = {
            "awaiting_confirmation": None, # 'order', 'parts', 'delete', 'update'
            "current_data": None,          # Data being processed (e.g. order data)
            "pending_parts": [],           # Parts waiting to be added
            "current_op": None,            # Current OP being worked on
            "candidate": None,             # Item candidate for delete/update
            "partial_update": None         # Partial update info
        }

    def process_input(self, user_message, attached_file=None, chat_history=[]):
        """
        Main entry point. Processes user input and returns a response.
        Returns:
            dict: {
                "response": str,       # Text response to user
                "action_taken": str,   # Internal action code (optional)
                "data": dict           # Any relevant data (optional)
            }
        """
        response_text = ""
        
        # 1. Handle File Attachment (Disabled)
        if attached_file:
             return {"response": "⚠️ O processamento de arquivos PDF foi desativado."}

        # 2. Handle Confirmations (if waiting)
        if self.state.get("awaiting_confirmation"):
            return self._handle_confirmation(user_message)

        # 3. Handle Partial Updates (if waiting for value)
        if self.state.get("partial_update"):
            return self._handle_partial_update(user_message)

        # 4. General Intent Processing
        # Use AI to understand intent
        extraction_result = extract_data_from_message(
            user_message, 
            self.state.get("current_data"), 
            chat_history
        )
        
        if not extraction_result:
             return {"response": "Desculpe, não entendi. Poderia reformular?"}

        # Dispatch based on intent
        if extraction_result.get("is_order_intent"):
            return self._handle_order_intent(extraction_result)
            
        elif extraction_result.get("is_search_intent"):
            return self._handle_search_intent(extraction_result)
            
        elif extraction_result.get("is_delete_intent"):
            return self._handle_delete_intent(extraction_result)
            
        elif extraction_result.get("is_update_intent"):
            return self._handle_update_intent(extraction_result)
            
        elif extraction_result.get("is_add_part_intent"):
             # Logic to add parts to existing order context could go here
             # For now, let's treat it as general or part of order flow
             pass

        # Default fallback - Conversational AI
        chat_response = get_chat_response(user_message, chat_history)
        return {"response": chat_response}

    def _handle_confirmation(self, user_message):
        msg_lower = user_message.lower()
        is_yes = any(k in msg_lower for k in ["sim", "s", "yes", "ok", "pode", "confirm"])
        is_no = any(k in msg_lower for k in ["não", "nao", "no", "cancel"])
        
        confirm_type = self.state["awaiting_confirmation"]
        
        if is_no:
            self._reset_state()
            return {"response": "Operação cancelada."}
            
        if not is_yes:
            # If not clearly yes or no, maybe it's a correction?
            # For simplicity in this refactor, we ask again or try to update.
            # Let's assume strict confirmation for now to keep it robust.
            return {"response": "Por favor, responda com 'Sim' para confirmar ou 'Não' para cancelar."}

        # Process Confirmation
        if confirm_type == "order":
            return self._finalize_create_order()
            
        elif confirm_type == "parts":
            return self._finalize_create_parts()
            
        elif confirm_type == "delete":
            return self._finalize_delete()
            
        elif confirm_type == "update":
            return self._finalize_update()
            
        elif confirm_type == "post_order_parts":
            # User said YES to adding parts.
            # We don't have parts yet, so we just acknowledge and guide them.
            self.state["awaiting_confirmation"] = None
            return {"response": "Ótimo! Por favor, informe as peças que deseja adicionar (Nome e Quantidade)."}

        return {"response": "Erro de estado."}

    def _finalize_create_order(self):
        data = self.state["current_data"]
        # Separate order and parts
        order_payload = {k: v for k, v in data.items() if k != "pecas"}
        parts_payload = data.get("pecas", [])
        
        res = create_order(order_payload)
        if res and res.status_code == 200:
            op_code = res.json()["codigo_op"]
            self.state["current_op"] = op_code
            
            if parts_payload:
                self.state["pending_parts"] = parts_payload
                self.state["awaiting_confirmation"] = "parts"
                self.state["current_data"] = None # Clear order data
                
                msg = f"✅ **Ordem (OP) criada! Código: `{op_code}`**\n\nIdentifiquei {len(parts_payload)} peças. Deseja cadastrá-las agora?"
                return {"response": msg}
            else:
                self._reset_state()
                # Keep the OP in context and wait for confirmation
                self.state["current_op"] = op_code 
                self.state["awaiting_confirmation"] = "post_order_parts"
                return {"response": f"✅ **Ordem (OP) criada! Código: `{op_code}`**\n\nDeseja cadastrar as peças para este pedido agora?"}
        else:
            err = res.text if res else "Erro desconhecido"
            return {"response": f"Erro ao criar ordem: {err}"}

    def _finalize_create_parts(self):
        if not self.state["current_op"] or not self.state["pending_parts"]:
            return {"response": "Erro: Dados de peças perdidos."}
            
        payload = {
            "codigo_op": self.state["current_op"],
            "pecas": self.state["pending_parts"]
        }
        
        res = create_parts(payload)
        if res and res.status_code == 200:
            self._reset_state()
            return {"response": "✅ **Peças cadastradas com sucesso!**\n\nO sistema agora está monitorando esta produção."}
        else:
            return {"response": f"Erro ao criar peças: {res.text if res else 'Erro desconhecido'}"}

    def _finalize_delete(self):
        candidate = self.state["candidate"]
        if not candidate: return {"response": "Erro: Item perdido."}
        
        if candidate["type"] == "order":
            res = delete_order(candidate["data"]["codigo_op"])
        else:
            res = delete_part(candidate["data"]["id_peca"])
            
        self._reset_state()
        if res and res.status_code == 200:
            return {"response": "✅ Item deletado com sucesso!"}
        else:
            return {"response": "❌ Erro ao deletar item."}

    def _finalize_update(self):
        candidate = self.state["candidate"]
        if not candidate: return {"response": "Erro: Item perdido."}
        
        if candidate["type"] == "order":
            res = update_order(candidate["data"]["codigo_op"], candidate["fields"])
        else:
            res = update_part(candidate["data"]["id_peca"], candidate["fields"])
            
        self._reset_state()
        if res and res.status_code == 200:
            return {"response": "✅ Item atualizado com sucesso!"}
        else:
            return {"response": "❌ Erro ao atualizar item."}

    def _handle_order_intent(self, result):
        data = result.get("data")
        missing = result.get("missing_fields", [])
        
        if not missing:
            self.state["current_data"] = data
            self.state["awaiting_confirmation"] = "order"
            
            msg = f"""📝 **Pedido Completo!**
            
**Dados identificados:**
- 👤 Cliente: {data.get('nome_cliente')}
- 📋 Pedido nº: {data.get('numero_pedido')}
- 📅 Data do Pedido: {data.get('data_pedido')}
- 🚚 Data de Entrega: {data.get('data_entrega')}
- 💰 Valor Total: R$ {data.get('preco_total', 0):.2f}

Deseja criar a Ordem de Produção com estes dados?"""
            return {"response": msg}
        else:
            # Update current partial data
            self.state["current_data"] = data
            question = result.get("missing_message") or f"Faltam dados: {', '.join(missing)}."
            return {"response": question}

    def _handle_search_intent(self, result):
        query = result.get("search_query")
        orders = search_orders(query)
        parts = search_parts(query)
        
        if not orders and not parts:
            return {"response": f"❌ Nenhum resultado encontrado para '{query}'."}
            
        msg = f"✅ **Resultados para '{query}':**\n\n"
        
        if orders:
            msg += "**📋 Pedidos Encontrados:**\n"
            for o in orders:
                msg += f"**🔹 OP:** `{o['codigo_op']}` | **Cliente:** {o['nome_cliente']} | **Status:** {o['status']}\n"
                
        if parts:
            msg += "\n**📦 Peças Encontradas:**\n"
            for p in parts:
                msg += f"- **Peça:** {p['nome_peca']} | **OP:** `{p['codigo_op']}`\n"
                
        return {"response": msg}

    def _handle_delete_intent(self, result):
        target = result.get("delete_target")
        query = result.get("delete_query")
        
        candidates_orders = []
        candidates_parts = []
        
        if target in ["order", "any"]:
            candidates_orders = search_orders(query)
        if target in ["part", "any"]:
            candidates_parts = search_parts(query)
            
        total = len(candidates_orders) + len(candidates_parts)
        
        if total == 0:
            return {"response": f"❌ Nada encontrado com '{query}' para deletar."}
        elif total == 1:
            if candidates_orders:
                item = candidates_orders[0]
                self.state["candidate"] = {"type": "order", "data": item}
                msg = f"⚠️ **Confirmar exclusão?**\n\n**Pedido:** {item['codigo_op']} | **Cliente:** {item['nome_cliente']}"
            else:
                item = candidates_parts[0]
                self.state["candidate"] = {"type": "part", "data": item}
                msg = f"⚠️ **Confirmar exclusão?**\n\n**Peça:** {item['nome_peca']} | **OP:** {item['codigo_op']}"
            
            self.state["awaiting_confirmation"] = "delete"
            return {"response": msg}
        else:
            return {"response": f"⚠️ Encontrei {total} itens. Seja mais específico."}

    def _handle_update_intent(self, result):
        target = result.get("update_target")
        query = result.get("update_query")
        fields = result.get("update_fields", {})
        missing_val = result.get("missing_update_value")
        
        if missing_val:
            self.state["partial_update"] = {
                "target": target,
                "query": query,
                "field": missing_val
            }
            return {"response": f"Para qual valor deseja alterar **{missing_val}**?"}
            
        # Search for item to update
        candidates_orders = []
        candidates_parts = []
        
        if target in ["order", "any"]:
            candidates_orders = search_orders(query)
        if target in ["part", "any"]:
            candidates_parts = search_parts(query)
            
        total = len(candidates_orders) + len(candidates_parts)
        
        if total == 1:
            if candidates_orders:
                item = candidates_orders[0]
                self.state["candidate"] = {"type": "order", "data": item, "fields": fields}
                changes = ", ".join([f"{k}: {v}" for k,v in fields.items()])
                msg = f"⚠️ **Confirmar alteração?**\n\n**Pedido:** {item['codigo_op']}\n**Mudanças:** {changes}"
            else:
                item = candidates_parts[0]
                self.state["candidate"] = {"type": "part", "data": item, "fields": fields}
                changes = ", ".join([f"{k}: {v}" for k,v in fields.items()])
                msg = f"⚠️ **Confirmar alteração?**\n\n**Peça:** {item['nome_peca']}\n**Mudanças:** {changes}"
                
            self.state["awaiting_confirmation"] = "update"
            return {"response": msg}
        elif total == 0:
            return {"response": f"❌ Nada encontrado com '{query}' para editar."}
        else:
            return {"response": f"⚠️ Encontrei {total} itens. Seja mais específico."}

    def _handle_partial_update(self, value):
        partial = self.state["partial_update"]
        field = partial["field"]
        
        # Construct full update intent result manually to reuse logic
        result = {
            "is_update_intent": True,
            "update_target": partial["target"],
            "update_query": partial["query"],
            "update_fields": {field: value}
        }
        
        self.state["partial_update"] = None # Clear partial
        return self._handle_update_intent(result)

    def _reset_state(self):
        self.state = {
            "awaiting_confirmation": None,
            "current_data": None,
            "pending_parts": [],
            "current_op": None,
            "candidate": None,
            "partial_update": None
        }
