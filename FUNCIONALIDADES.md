# 📋 Documentação de Funcionalidades - Sistema de Monitoramento de Produção

## Visão Geral

O sistema é uma automação local para **acompanhamento de produção**, composto por:
- **Backend API** (FastAPI) - Gerencia todas as operações CRUD
- **Frontend Chat** (Streamlit) - Interface de chat com IA
- **Agente Inteligente** - Processa linguagem natural e executa ações
- **Banco de Dados** (Supabase) - Armazena todos os dados

---

## 🏭 Módulo 1: Gestão de Ordens de Produção (OP)

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Criar OP** | Cria nova ordem de produção com dados do cliente | `POST /orders` |
| **Buscar OP** | Pesquisa ordens por cliente ou código | `GET /orders/search` |
| **Ver OP** | Obtém detalhes de uma OP específica | `GET /orders/{codigo_op}` |
| **Atualizar OP** | Edita dados da ordem (cliente, data, status) | `PUT /orders/{codigo_op}` |
| **Deletar OP** | Remove ordem e todas as peças vinculadas | `DELETE /orders/{codigo_op}` |
| **Listar Peças da OP** | Obtém todas as peças de uma OP | `GET /orders/{codigo_op}/parts` |

### Campos da Ordem de Produção
- `nome_cliente` - Nome do cliente (obrigatório)
- `numero_pedido` - Número do pedido (obrigatório)
- `data_pedido` - Data do pedido
- `previsao_entrega` - Data prevista da entrega (obrigatório)
- `data_entrega` - Data real da entrega (preenchido apenas quando a entrega é realizada)
- `preco_total` - Valor total (obrigatório)
- `icms` - Valor do ICMS
- `status` - Status da ordem (Pendente, Em Produção, Concluído)
- `codigo_op` - Código único gerado automaticamente

---

## 📦 Módulo 2: Gestão de Peças

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Criar Peças** | Adiciona peças a uma OP existente | `POST /parts` |
| **Buscar Peças** | Pesquisa peças por nome, cliente ou status | `GET /parts/search` |
| **Atualizar Peça** | Edita dados da peça (quantidade, status) | `PUT /parts/{part_id}` |
| **Deletar Peça** | Remove uma peça específica | `DELETE /parts/{part_id}` |

### Campos da Peça
- `codigo_op` - Código da OP (obrigatório)
- `nome_peca` - Nome da peça (obrigatório)
- `quantidade` - Quantidade total (obrigatório)
- `preco_unitario` - Preço por unidade
- `status` - Status de produção
- `pecas_produzidas` - Quantidade já produzida
- `nome_cliente` - Herdado da OP
- `previsao_entrega` - Herdado da OP
- `data_entrega` - Preenchido quando a entrega é realizada

---

## 📚 Módulo 3: Catálogo de Itens

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Criar Item** | Adiciona novo item ao catálogo | `POST /catalog` |
| **Listar Itens** | Lista todos os itens (com filtros) | `GET /catalog` |
| **Ver Item** | Obtém detalhes de um item específico | `GET /catalog/{item_id}` |
| **Atualizar Item** | Edita dados do item | `PUT /catalog/{item_id}` |
| **Deletar Item** | Remove item do catálogo | `DELETE /catalog/{item_id}` |
| **Ver Tipos** | Lista tipos de itens disponíveis | `GET /catalog/types` |
| **Estatísticas** | Retorna estatísticas do catálogo | `GET /catalog/stats` |

### Tipos de Itens
- `Produto Final` - Itens fabricados (requer tempo de produção)
- `Itens Consumíveis` - Materiais de uso
- `Matérias Primas` - Insumos para produção
- `Inventário` - Outros itens

### Campos do Item do Catálogo
- `nome` - Nome do item (obrigatório)
- `preco` - Preço unitário (obrigatório)
- `tipo` - Tipo do item (obrigatório)
- `tempo_producao` - Tempo de produção (obrigatório para Produto Final)

---

## 📦 Módulo 4: Gestão de Estoque

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Adicionar ao Estoque** | Adiciona/atualiza quantidade de item | `POST /stock` |
| **Listar Estoque** | Lista itens em estoque (com filtros) | `GET /stock` |
| **Ver Item** | Obtém detalhes de um item no estoque | `GET /stock/{item_id}` |
| **Atualizar Quantidade** | Altera quantidade (set, add, subtract) | `PUT /stock/{item_id}` |
| **Remover do Estoque** | Remove item do estoque | `DELETE /stock/{item_id}` |
| **Estatísticas** | Retorna estatísticas do estoque | `GET /stock/stats` |
| **Verificar Disponibilidade** | Checa se item existe no catálogo/estoque | `GET /stock/check/{nome}` |

### Regras do Estoque
- **Pré-requisito**: O item deve existir no catálogo antes de ser adicionado ao estoque
- Ao adicionar item já existente, a quantidade é somada
- Preço e tipo são herdados automaticamente do catálogo

### Operações de Quantidade
- `set` - Define um valor fixo
- `add` - Soma à quantidade atual
- `subtract` - Subtrai da quantidade atual

---

## 🤖 Módulo 5: Agente de Chat Inteligente

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Processar Mensagem** | Interpreta e executa ações via chat | `POST /chat` |
| **Ver Contexto** | Retorna histórico e estado do usuário | `GET /context/{phone_number}` |
| **Webhook n8n** | Recebe mensagens do n8n | `POST /webhook/n8n` |

### Intents Reconhecidos
1. **Criar Pedido** - "Criar pedido para cliente X..."
2. **Cadastrar Peças** - "Adicionar 100 unidades de Eixo..."
3. **Buscar** - "Buscar pedidos do cliente Y..."
4. **Editar** - "Alterar data de entrega para..."
5. **Deletar** - "Remover pedido ABC123..."
6. **Catálogo** - "Cadastrar item no catálogo..."
7. **Estoque** - "Adicionar 50 unidades ao estoque..."

### Fluxo de Confirmação
O agente sempre solicita confirmação antes de:
- Criar uma nova OP
- Adicionar peças
- Atualizar dados
- Deletar itens

### Comandos de Ajuda
- `/menu` - Exibe todos os comandos disponíveis
- `/criar_pedido` - Ajuda sobre criação de pedido
- `/cadastrar_pecas` - Ajuda sobre cadastro de peças
- `/buscar` - Ajuda sobre busca
- `/editar` - Ajuda sobre edição
- `/deletar` - Ajuda sobre exclusão
- `/catalogo` - Ajuda sobre catálogo
- `/estoque` - Ajuda sobre estoque

---

## 🔔 Módulo 6: Análise e Alertas

### Funcionalidades

| Operação | Descrição | Endpoint API |
|----------|-----------|--------------|
| **Analisar Produção** | Identifica atrasos e gera alertas | `GET /analyze` |

### Regras de Alerta
- Peças com `previsao_entrega` anterior à data atual
- Status diferente de "Concluído"
- Calcula dias de atraso baseado na previsão de entrega

---

## 🔗 Módulo 7: Integrações

### n8n Webhook
- Permite integração com n8n para automação de fluxos
- Reusa a lógica do chat para processar mensagens
- Dispara webhook de retorno se configurado

### Variáveis de Ambiente
```
SUPABASE_URL=<URL do Supabase>
SUPABASE_KEY=<Chave do Supabase>
OPENAI_API_KEY=<Chave da OpenAI>
API_URL=http://localhost:8000
N8N_WEBHOOK_URL=<URL do webhook n8n (opcional)>
```

---

## 📊 Resumo de Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Health check |
| POST | `/orders` | Criar ordem |
| GET | `/orders/search` | Buscar ordens |
| GET | `/orders/{codigo_op}` | Obter ordem |
| PUT | `/orders/{codigo_op}` | Atualizar ordem |
| DELETE | `/orders/{codigo_op}` | Deletar ordem |
| GET | `/orders/{codigo_op}/parts` | Peças da ordem |
| POST | `/parts` | Criar peças |
| GET | `/parts/search` | Buscar peças |
| PUT | `/parts/{part_id}` | Atualizar peça |
| DELETE | `/parts/{part_id}` | Deletar peça |
| POST | `/catalog` | Criar item catálogo |
| GET | `/catalog` | Listar catálogo |
| GET | `/catalog/types` | Tipos de itens |
| GET | `/catalog/{item_id}` | Obter item catálogo |
| PUT | `/catalog/{item_id}` | Atualizar catálogo |
| DELETE | `/catalog/{item_id}` | Deletar catálogo |
| GET | `/catalog/stats` | Estatísticas catálogo |
| POST | `/stock` | Adicionar estoque |
| GET | `/stock` | Listar estoque |
| GET | `/stock/{item_id}` | Obter item estoque |
| PUT | `/stock/{item_id}` | Atualizar estoque |
| DELETE | `/stock/{item_id}` | Deletar estoque |
| GET | `/stock/stats` | Estatísticas estoque |
| GET | `/stock/check/{nome}` | Verificar disponibilidade |
| POST | `/chat` | Processar chat |
| GET | `/context/{phone}` | Obter contexto |
| POST | `/webhook/n8n` | Webhook n8n |
| GET | `/analyze` | Analisar produção |

---

*Versão: 0.0.7 | Última atualização: Janeiro 2026*
