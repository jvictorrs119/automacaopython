def format_order_confirmation(data):
    """Template for confirming order creation"""
    return f"""🏭 *Confirmar Criação de Pedido*

👤 *Cliente:* {data.get('nome_cliente', 'N/A')}
📋 *Pedido:* {data.get('numero_pedido', 'N/A')}
📅 *Data:* {data.get('data_pedido', 'N/A')}
🚚 *Entrega:* {data.get('data_entrega', 'N/A')}
💰 *Valor:* R$ {data.get('preco_total', 0):.2f}
💸 *ICMS:* {data.get('icms', 'N/A')}

Deseja confirmar a criação deste pedido? (Sim/Não)"""

def format_parts_confirmation(client_name, op_code, parts):
    """Template for confirming parts addition"""
    parts_list = "\n".join([f"• {p['quantidade']}x {p['nome_peca']} - R$ {p.get('preco_unitario', 0):.2f}" for p in parts])
    
    return f"""📦 *Confirmar Adição de Peças*

🏭 *Cliente:* {client_name}
📋 *OP:* {op_code}

*Peças Identificadas:*
{parts_list}

Deseja confirmar o cadastro destas peças? (Sim/Não)"""

def format_update_confirmation(item_type, identifier, changes):
    """Template for confirming update"""
    changes_list = "\n".join([f"• {k}: {v}" for k, v in changes.items()])
    
    return f"""✏️ *Confirmar Edição*

*Item:* {item_type} {identifier}
*Alterações:*
{changes_list}

Confirmar alteração? (Sim/Não)"""

def format_update_success(identifier):
    """Template for update success"""
    return f"""✅ *Edição Concluída!*

O item *{identifier}* foi atualizado com sucesso."""

def format_delete_confirmation(item_type, identifier, details):
    """Template for confirming deletion"""
    return f"""🗑️ *Confirmar Exclusão*

Você está prestes a deletar:
*Tipo:* {item_type}
*Item:* {identifier}
*Detalhes:* {details}

⚠️ Esta ação não pode ser desfeita. Confirmar? (Sim/Não)"""

def format_delete_success(identifier):
    """Template for deletion success"""
    return f"""✅ *Exclusão Realizada*

O item *{identifier}* foi removido do sistema."""

def format_search_results(query, orders, parts):
    """Template for search results"""
    total = len(orders) + len(parts)
    msg = f"🔍 *Resultado da Busca*\n\nEncontrei {total} itens para \"{query}\":\n"
    
    if orders:
        msg += "\n*Pedidos:*\n"
        for o in orders:
            msg += f"• *OP:* `{o['codigo_op']}` | *Cliente:* {o['nome_cliente']} | *Status:* {o['status']}\n"
            
    if parts:
        msg += "\n*Peças:*\n"
        for p in parts:
            msg += f"• *Peça:* {p['nome_peca']} | *OP:* `{p['codigo_op']}`\n"
            
    return msg
