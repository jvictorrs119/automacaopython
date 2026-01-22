"""
Módulo de Comandos de Ajuda
Sistema de menu para guiar usuários nas funcionalidades da ferramenta.
"""

# Dicionário com todos os comandos e suas explicações
HELP_COMMANDS = {
    "/menu": {
        "titulo": "📋 Menu Principal",
        "descricao": "Exibe a lista de todos os comandos disponíveis."
    },
    "/criar_pedido": {
        "titulo": "🏭 Criar Pedido (OP)",
        "descricao": """Esta funcionalidade permite criar uma nova Ordem de Produção (OP).

**Como usar:**
Basta informar os dados do pedido em linguagem natural. Por exemplo:
- "Criar pedido para cliente João, número 12345, entrega dia 20/12/2025, valor R$ 5000"
- "Novo pedido: Cliente Maria, pedido 67890, data 15/01/2026, total R$ 3500"

**Campos obrigatórios:**
• Nome do Cliente
• Número do Pedido
• Data do Pedido
• Data de Entrega
• Valor Total

**O que acontece:**
1. O sistema extrai os dados da sua mensagem
2. Solicita confirmação antes de criar
3. Gera um código OP único (ex: ABC123)
4. Pergunta se deseja cadastrar as peças do pedido"""
    },
    "/cadastrar_pecas": {
        "titulo": "📦 Cadastrar Peças",
        "descricao": """Esta funcionalidade permite adicionar peças a uma Ordem de Produção existente.

**Como usar:**
Após criar um pedido, você pode cadastrar as peças informando:
- "Adicionar 100 unidades de Eixo Central a R$ 25 cada"
- "Cadastrar peças: 50 Flanges, 30 Buchas, 20 Rolamentos"

**Campos obrigatórios:**
• Nome da Peça
• Quantidade
• (Opcional) Preço Unitário

**O que acontece:**
1. As peças são vinculadas à OP ativa
2. O sistema começa a monitorar a produção
3. Você pode acompanhar o progresso de cada peça"""
    },
    "/buscar": {
        "titulo": "🔍 Buscar Itens",
        "descricao": """Esta funcionalidade permite buscar pedidos e peças no sistema.

**Como usar:**
- "Buscar pedidos do cliente João"
- "Procurar OP ABC123"
- "Listar peças em produção"
- "Encontrar pedidos atrasados"

**Você pode buscar por:**
• Nome do cliente
• Código da OP
• Nome da peça
• Status (Em Produção, Pendente, Concluído)

**Resultado:**
O sistema retorna uma lista com os itens encontrados, mostrando código, cliente e status."""
    },
    "/editar": {
        "titulo": "✏️ Editar Itens",
        "descricao": """Esta funcionalidade permite editar pedidos e peças existentes.

**Como usar:**
1. Primeiro, busque o item que deseja editar
2. Depois solicite a alteração:
   - "Editar a data de entrega para 25/12/2025"
   - "Alterar quantidade para 150 unidades"
   - "Mudar status para Concluído"

**Campos editáveis em Pedidos:**
• Nome do cliente
• Data de entrega
• Valor total
• Status

**Campos editáveis em Peças:**
• Nome da peça
• Quantidade
• Peças produzidas
• Status"""
    },
    "/deletar": {
        "titulo": "🗑️ Deletar Itens",
        "descricao": """Esta funcionalidade permite remover pedidos e peças do sistema.

**Como usar:**
1. Primeiro, busque o item que deseja deletar
2. Depois solicite a exclusão:
   - "Deletar este pedido"
   - "Remover a peça selecionada"
   - "Excluir OP ABC123"

**⚠️ Atenção:**
• Ao deletar um pedido (OP), todas as peças vinculadas também são removidas
• O sistema sempre pedirá confirmação antes de excluir
• Esta ação não pode ser desfeita"""
    },
    "/catalogo": {
        "titulo": "📚 Catálogo de Itens",
        "descricao": """Esta funcionalidade permite gerenciar o catálogo de itens da empresa.

**Como usar:**
- "Cadastrar item no catálogo: Parafuso M10, preço R$ 0.50, tipo Consumível"
- "Listar itens do catálogo"
- "Ver catálogo de produtos finais"

**Tipos de itens:**
• Produto Final - itens fabricados (requer tempo de produção)
• Itens Consumíveis - materiais de uso
• Matérias Primas - insumos para produção
• Inventário - outros itens

**Campos obrigatórios:**
• Nome do item
• Preço
• Tipo

**Importante:**
Para adicionar itens ao estoque, eles devem estar cadastrados no catálogo primeiro."""
    },
    "/estoque": {
        "titulo": "📦 Gestão de Estoque",
        "descricao": """Esta funcionalidade permite gerenciar o estoque de itens.

**Como usar:**
- "Adicionar 100 unidades de Parafuso M10 ao estoque"
- "Ver estoque atual"
- "Verificar estoque de Parafusos"
- "Listar itens no estoque"

**Operações disponíveis:**
• Adicionar itens ao estoque
• Consultar quantidade disponível
• Listar todos os itens em estoque
• Verificar valor total em estoque

**Pré-requisito:**
O item deve existir no catálogo antes de ser adicionado ao estoque."""
    }
}


def get_menu_help():
    """Retorna o menu principal com todos os comandos disponíveis"""
    menu = """📋 *Menu de Comandos - Assistente de Produção*

Bem-vindo! Aqui estão todos os comandos disponíveis para ajudá-lo:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏭 **Gestão de Pedidos:**
• `/criar_pedido` - Como criar uma nova Ordem de Produção
• `/cadastrar_pecas` - Como adicionar peças a um pedido

🔍 **Consultas:**
• `/buscar` - Como buscar pedidos e peças

✏️ **Edição:**
• `/editar` - Como editar itens existentes
• `/deletar` - Como remover itens do sistema

📚 **Catálogo e Estoque:**
• `/catalogo` - Como gerenciar o catálogo de itens
• `/estoque` - Como gerenciar o estoque

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Dica:* Digite qualquer comando acima para ver instruções detalhadas.

*Exemplo:* Digite `/criar_pedido` para aprender como criar um pedido."""
    
    return menu


def get_command_help(command: str):
    """
    Retorna a ajuda para um comando específico.
    
    Args:
        command: O comando digitado pelo usuário (ex: /criar_pedido)
    
    Returns:
        str: Texto de ajuda ou None se comando não existir
    """
    # Normaliza o comando
    cmd = command.strip().lower()
    
    # Busca no dicionário
    if cmd in HELP_COMMANDS:
        info = HELP_COMMANDS[cmd]
        return f"""{info['titulo']}

{info['descricao']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Digite `/menu` para ver todos os comandos disponíveis."""
    
    return None


def is_help_command(message: str) -> bool:
    """Verifica se a mensagem é um comando de ajuda"""
    return message.strip().startswith("/")
