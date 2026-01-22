def format_order_confirmation(data):
    """Template for confirming order creation"""
    return f"""🏭 *Confirmar Criação de Pedido*

👤 *Cliente:* {data.get('nome_cliente', 'N/A')}
📋 *Pedido:* {data.get('numero_pedido', 'N/A')}
📅 *Data:* {data.get('data_pedido', 'N/A')}
🚚 *Previsão de Entrega:* {data.get('previsao_entrega', 'N/A')}
💰 *Valor:* R$ {data.get('preco_total', 0):.2f}
💸 *ICMS:* {data.get('icms', 'N/A')}

Deseja confirmar a criação deste pedido? (Sim/Não)"""

def format_order_created_success(codigo_op, pecas=None):
    """Template for order creation success with optional parts detected"""
    msg = f"""✅ *Ordem (OP) criada com sucesso!*

🏭 *Código da OP:* `{codigo_op}`"""
    
    if pecas and len(pecas) > 0:
        msg += "\n\n📦 *Peças identificadas na sua mensagem:*\n\n"
        for i, p in enumerate(pecas, start=1):
            qtd = p.get('quantidade', 0)
            nome = p.get('nome_peca', 'N/A')
            preco = p.get('preco_unitario', 0)
            if preco:
                msg += f"**{i}.** {qtd}x *{nome}* - R$ {preco:.2f}\n"
            else:
                msg += f"**{i}.** {qtd}x *{nome}*\n"
        
        msg += """
🔄 Deseja cadastrar essas peças agora? (Sim/Não)"""
    else:
        msg += """

📦 Deseja cadastrar as peças para este pedido agora? (Sim/Não)"""
    
    return msg

def format_parts_confirmation(client_name, op_code, parts):
    """Template for confirming parts addition"""
    parts_list = "\n".join([f"**{i}.** {p['quantidade']}x {p['nome_peca']} - R$ {p.get('preco_unitario', 0):.2f}" for i, p in enumerate(parts, start=1)])
    
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
