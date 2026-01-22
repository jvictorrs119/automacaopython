# 🧪 Rotina de Testes - Sistema de Monitoramento de Produção

Este documento contém os cenários de teste para validar todas as funcionalidades do sistema.

---

## 📋 Pré-requisitos

1. **Ambiente configurado**
   - Python virtual environment ativo
   - Dependências instaladas (`pip install -r requirements.txt`)
   - Variáveis de ambiente configuradas no `.env`

2. **Serviços iniciados**
   - API rodando: `.\start_api.ps1`
   - Streamlit rodando: `.\start_streamlit.ps1`

3. **Acesso**
   - API: http://localhost:8000
   - Frontend: http://localhost:8501
   - Docs API: http://localhost:8000/docs

---

## 🏭 Testes do Módulo 1: Ordens de Produção (OP)

### T1.1 - Criar Ordem de Produção via Chat
| ID | T1.1 |
|----|------|
| **Objetivo** | Verificar criação de OP via interface de chat |
| **Pré-condição** | Sistema rodando, nenhuma OP com os dados do teste |
| **Passos** | 1. Abrir Streamlit (http://localhost:8501)<br>2. Digitar: "Criar pedido para cliente **Teste Ltda**, número **99999**, entrega dia **30/03/2026**, valor **R$ 5000**"<br>3. Aguardar resposta do agente<br>4. Confirmar digitando "Sim" |
| **Resultado Esperado** | Sistema confirma criação com código OP único (ex: ABC123) |
| **Status** | ⬜ Pendente |

### T1.2 - Buscar Ordem de Produção
| ID | T1.2 |
|----|------|
| **Objetivo** | Verificar busca de OP por nome do cliente |
| **Pré-condição** | OP criada no teste T1.1 |
| **Passos** | 1. Digitar: "Buscar pedidos do cliente **Teste Ltda**" |
| **Resultado Esperado** | Sistema retorna lista com a OP criada, mostrando código, cliente e status |
| **Status** | ⬜ Pendente |

### T1.3 - Buscar OP por Código
| ID | T1.3 |
|----|------|
| **Objetivo** | Verificar busca de OP por código |
| **Pré-condição** | OP criada no teste T1.1 |
| **Passos** | 1. Digitar: "Buscar OP **[código da OP criada]**" |
| **Resultado Esperado** | Sistema retorna detalhes da OP específica |
| **Status** | ⬜ Pendente |

### T1.4 - Editar Ordem de Produção
| ID | T1.4 |
|----|------|
| **Objetivo** | Verificar edição de dados da OP |
| **Pré-condição** | OP encontrada no teste T1.2 ou T1.3 |
| **Passos** | 1. Digitar: "Alterar a data de entrega para **15/04/2026**"<br>2. Confirmar digitando "Sim" |
| **Resultado Esperado** | Sistema confirma atualização com os novos dados |
| **Status** | ⬜ Pendente |

### T1.5 - Editar Status da OP
| ID | T1.5 |
|----|------|
| **Objetivo** | Verificar alteração de status |
| **Pré-condição** | OP existente |
| **Passos** | 1. Digitar: "Buscar OP **[código]**"<br>2. Digitar: "Alterar status para **Em Produção**"<br>3. Confirmar |
| **Resultado Esperado** | Status atualizado para "Em Produção" |
| **Status** | ⬜ Pendente |

### T1.6 - Deletar Ordem de Produção
| ID | T1.6 |
|----|------|
| **Objetivo** | Verificar exclusão de OP |
| **Pré-condição** | OP de teste existente |
| **Passos** | 1. Digitar: "Deletar OP **[código]**"<br>2. Confirmar digitando "Sim" |
| **Resultado Esperado** | Sistema confirma exclusão da OP e peças vinculadas |
| **Status** | ⬜ Pendente |

---

## 📦 Testes do Módulo 2: Peças

### T2.1 - Cadastrar Peças em Nova OP
| ID | T2.1 |
|----|------|
| **Objetivo** | Verificar cadastro de peças junto com OP |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Criar nova OP: "Criar pedido cliente **Indústria X**, pedido **88888**, entrega **20/04/2026**, valor **R$ 10000**"<br>2. Confirmar criação<br>3. Quando perguntar sobre peças, digitar: "Sim, adicionar **50 unidades de Eixo Central** a **R$ 25** cada e **100 unidades de Bucha** a **R$ 10** cada"<br>4. Confirmar cadastro |
| **Resultado Esperado** | Peças cadastradas e vinculadas à OP |
| **Status** | ⬜ Pendente |

### T2.2 - Adicionar Peças a OP Existente
| ID | T2.2 |
|----|------|
| **Objetivo** | Verificar adição de peças a OP existente |
| **Pré-condição** | OP criada sem peças |
| **Passos** | 1. Digitar: "Adicionar **30 unidades de Flange** a **R$ 50** cada na OP **[código]**"<br>2. Confirmar |
| **Resultado Esperado** | Nova peça adicionada à OP existente |
| **Status** | ⬜ Pendente |

### T2.3 - Buscar Peças por Nome
| ID | T2.3 |
|----|------|
| **Objetivo** | Verificar busca de peças |
| **Pré-condição** | Peças cadastradas |
| **Passos** | 1. Digitar: "Buscar peças **Eixo**" |
| **Resultado Esperado** | Lista de peças com "Eixo" no nome |
| **Status** | ⬜ Pendente |

### T2.4 - Editar Quantidade de Peça
| ID | T2.4 |
|----|------|
| **Objetivo** | Verificar edição de quantidade |
| **Pré-condição** | Peça existente |
| **Passos** | 1. Buscar a peça<br>2. Digitar: "Alterar quantidade para **75 unidades**"<br>3. Confirmar |
| **Resultado Esperado** | Quantidade atualizada |
| **Status** | ⬜ Pendente |

### T2.5 - Atualizar Peças Produzidas
| ID | T2.5 |
|----|------|
| **Objetivo** | Verificar atualização de progresso |
| **Pré-condição** | Peça existente |
| **Passos** | 1. Buscar a peça<br>2. Digitar: "Atualizar **peças produzidas** para **25**"<br>3. Confirmar |
| **Resultado Esperado** | Campo peças_produzidas atualizado |
| **Status** | ⬜ Pendente |

### T2.6 - Deletar Peça
| ID | T2.6 |
|----|------|
| **Objetivo** | Verificar exclusão de peça individual |
| **Pré-condição** | Peça existente |
| **Passos** | 1. Buscar a peça<br>2. Digitar: "Deletar esta peça"<br>3. Confirmar |
| **Resultado Esperado** | Peça removida, OP mantida |
| **Status** | ⬜ Pendente |

---

## 📚 Testes do Módulo 3: Catálogo

### T3.1 - Criar Item Tipo Produto Final
| ID | T3.1 |
|----|------|
| **Objetivo** | Verificar criação de item com tempo de produção |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "Cadastrar no catálogo: **Engrenagem M20**, preço **R$ 150**, tipo **Produto Final**, tempo de produção **60 minutos**" |
| **Resultado Esperado** | Item criado com todos os campos |
| **Status** | ⬜ Pendente |

### T3.2 - Criar Item Tipo Consumível
| ID | T3.2 |
|----|------|
| **Objetivo** | Verificar criação de item consumível |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "Cadastrar no catálogo: **Parafuso M10**, preço **R$ 0.50**, tipo **Consumível**" |
| **Resultado Esperado** | Item criado sem tempo de produção |
| **Status** | ⬜ Pendente |

### T3.3 - Criar Item Tipo Matéria Prima
| ID | T3.3 |
|----|------|
| **Objetivo** | Verificar criação de matéria prima |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "Cadastrar no catálogo: **Barra de Aço 1020**, preço **R$ 80**, tipo **Matéria Prima**" |
| **Resultado Esperado** | Item criado corretamente |
| **Status** | ⬜ Pendente |

### T3.4 - Listar Catálogo por Tipo
| ID | T3.4 |
|----|------|
| **Objetivo** | Verificar filtro por tipo |
| **Pré-condição** | Itens de diferentes tipos cadastrados |
| **Passos** | 1. Digitar: "Listar itens do tipo **Consumível** no catálogo" |
| **Resultado Esperado** | Lista apenas itens consumíveis |
| **Status** | ⬜ Pendente |

### T3.5 - Buscar Item no Catálogo
| ID | T3.5 |
|----|------|
| **Objetivo** | Verificar busca por nome |
| **Pré-condição** | Itens cadastrados |
| **Passos** | 1. Digitar: "Buscar **Parafuso** no catálogo" |
| **Resultado Esperado** | Retorna itens com "Parafuso" no nome |
| **Status** | ⬜ Pendente |

### T3.6 - Editar Item do Catálogo
| ID | T3.6 |
|----|------|
| **Objetivo** | Verificar edição de item |
| **Pré-condição** | Item existente |
| **Passos** | 1. Buscar item<br>2. Digitar: "Alterar preço para **R$ 0.75**"<br>3. Confirmar |
| **Resultado Esperado** | Preço atualizado |
| **Status** | ⬜ Pendente |

### T3.7 - Deletar Item do Catálogo
| ID | T3.7 |
|----|------|
| **Objetivo** | Verificar exclusão |
| **Pré-condição** | Item existente sem estoque vinculado |
| **Passos** | 1. Digitar: "Remover **[nome item]** do catálogo"<br>2. Confirmar |
| **Resultado Esperado** | Item removido |
| **Status** | ⬜ Pendente |

### T3.8 - Ver Estatísticas do Catálogo
| ID | T3.8 |
|----|------|
| **Objetivo** | Verificar estatísticas |
| **Pré-condição** | Itens cadastrados |
| **Passos** | 1. Acessar endpoint `/catalog/stats` via Swagger (http://localhost:8000/docs) |
| **Resultado Esperado** | Retorna quantidade e valor total por tipo |
| **Status** | ⬜ Pendente |

---

## 📦 Testes do Módulo 4: Estoque

### T4.1 - Adicionar Item ao Estoque
| ID | T4.1 |
|----|------|
| **Objetivo** | Verificar adição de item existente no catálogo |
| **Pré-condição** | Item "Parafuso M10" no catálogo (teste T3.2) |
| **Passos** | 1. Digitar: "Adicionar **100 unidades** de **Parafuso M10** ao estoque" |
| **Resultado Esperado** | Item adicionado ao estoque com preço do catálogo |
| **Status** | ⬜ Pendente |

### T4.2 - Adicionar Item Inexistente (Erro)
| ID | T4.2 |
|----|------|
| **Objetivo** | Verificar validação de item no catálogo |
| **Pré-condição** | Item não existe no catálogo |
| **Passos** | 1. Digitar: "Adicionar **50** de **Item Inexistente XYZ** ao estoque" |
| **Resultado Esperado** | Erro informando que item deve ser cadastrado no catálogo primeiro |
| **Status** | ⬜ Pendente |

### T4.3 - Somar Quantidade ao Estoque
| ID | T4.3 |
|----|------|
| **Objetivo** | Verificar soma de quantidade |
| **Pré-condição** | Item já no estoque (teste T4.1) |
| **Passos** | 1. Digitar: "Adicionar mais **50** de **Parafuso M10** ao estoque" |
| **Resultado Esperado** | Quantidade total = 150 unidades |
| **Status** | ⬜ Pendente |

### T4.4 - Listar Estoque
| ID | T4.4 |
|----|------|
| **Objetivo** | Verificar listagem |
| **Pré-condição** | Itens no estoque |
| **Passos** | 1. Digitar: "Ver estoque atual" |
| **Resultado Esperado** | Lista de itens com quantidade e valor |
| **Status** | ⬜ Pendente |

### T4.5 - Verificar Item no Estoque
| ID | T4.5 |
|----|------|
| **Objetivo** | Verificar consulta específica |
| **Pré-condição** | Item no estoque |
| **Passos** | 1. Digitar: "Verificar estoque de **Parafuso**" |
| **Resultado Esperado** | Quantidade disponível do item |
| **Status** | ⬜ Pendente |

### T4.6 - Atualizar Quantidade (Subtrair)
| ID | T4.6 |
|----|------|
| **Objetivo** | Verificar operação de subtração |
| **Pré-condição** | Item com quantidade > 0 |
| **Passos** | 1. Via API (Swagger): `PUT /stock/{item_id}` com `{\"quantidade\": 20, \"operacao\": \"subtract\"}` |
| **Resultado Esperado** | Quantidade reduzida em 20 unidades |
| **Status** | ⬜ Pendente |

### T4.7 - Remover Item do Estoque
| ID | T4.7 |
|----|------|
| **Objetivo** | Verificar remoção |
| **Pré-condição** | Item no estoque |
| **Passos** | 1. Via API (Swagger): `DELETE /stock/{item_id}` |
| **Resultado Esperado** | Item removido do estoque (permanece no catálogo) |
| **Status** | ⬜ Pendente |

### T4.8 - Ver Estatísticas do Estoque
| ID | T4.8 |
|----|------|
| **Objetivo** | Verificar estatísticas |
| **Pré-condição** | Itens no estoque |
| **Passos** | 1. Acessar endpoint `/stock/stats` via Swagger |
| **Resultado Esperado** | Quantidade total e valor por tipo |
| **Status** | ⬜ Pendente |

---

## 🤖 Testes do Módulo 5: Agente de Chat

### T5.1 - Comando /menu
| ID | T5.1 |
|----|------|
| **Objetivo** | Verificar menu de ajuda |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "**/menu**" |
| **Resultado Esperado** | Lista de todos os comandos disponíveis |
| **Status** | ⬜ Pendente |

### T5.2 - Comando de Ajuda Específico
| ID | T5.2 |
|----|------|
| **Objetivo** | Verificar ajuda de comando |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "**/criar_pedido**" |
| **Resultado Esperado** | Instruções detalhadas sobre criação de pedido |
| **Status** | ⬜ Pendente |

### T5.3 - Cancelar Operação
| ID | T5.3 |
|----|------|
| **Objetivo** | Verificar cancelamento de confirmação |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Iniciar criação de pedido<br>2. Quando pedir confirmação, digitar: "**Não**" ou "**Cancelar**" |
| **Resultado Esperado** | Operação cancelada, estado limpo |
| **Status** | ⬜ Pendente |

### T5.4 - Conversa Natural
| ID | T5.4 |
|----|------|
| **Objetivo** | Verificar resposta a mensagens não-operacionais |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "Olá, bom dia!" |
| **Resultado Esperado** | Resposta cordial e orientação sobre funções |
| **Status** | ⬜ Pendente |

### T5.5 - Contexto de Conversa
| ID | T5.5 |
|----|------|
| **Objetivo** | Verificar manutenção de contexto |
| **Pré-condição** | Resultado de busca anterior |
| **Passos** | 1. Buscar um pedido<br>2. Sem mencionar o código, digitar: "Editar a data de entrega para amanhã" |
| **Resultado Esperado** | Sistema usa contexto da busca anterior |
| **Status** | ⬜ Pendente |

### T5.6 - Múltiplas Intenções
| ID | T5.6 |
|----|------|
| **Objetivo** | Verificar processamento de mensagem complexa |
| **Pré-condição** | Nenhuma |
| **Passos** | 1. Digitar: "Criar pedido para cliente ABC, número 12345, entrega 01/06/2026, valor R$ 8000, com 100 peças Flange a R$ 50 cada" |
| **Resultado Esperado** | Sistema extrai dados do pedido E das peças |
| **Status** | ⬜ Pendente |

---

## 🔔 Testes do Módulo 6: Análise e Alertas

### T6.1 - Verificar Alertas
| ID | T6.1 |
|----|------|
| **Objetivo** | Verificar identificação de atrasos |
| **Pré-condição** | Peça com data de entrega no passado e status não concluído |
| **Passos** | 1. Criar OP com data de entrega passada<br>2. Acessar endpoint `/analyze` via Swagger |
| **Resultado Esperado** | Lista de alertas com peças atrasadas |
| **Status** | ⬜ Pendente |

### T6.2 - Botão Verificar Alertas (Streamlit)
| ID | T6.2 |
|----|------|
| **Objetivo** | Verificar função de alertas na interface |
| **Pré-condição** | Peças atrasadas no sistema |
| **Passos** | 1. Clicar no botão "Verificar Alertas" na barra lateral |
| **Resultado Esperado** | Exibe lista de alertas na interface |
| **Status** | ⬜ Pendente |

---

## 🔗 Testes do Módulo 7: API REST

### T7.1 - Health Check
| ID | T7.1 |
|----|------|
| **Objetivo** | Verificar se API está rodando |
| **Pré-condição** | API iniciada |
| **Passos** | 1. Acessar `GET /` via navegador ou curl |
| **Resultado Esperado** | Resposta JSON de sucesso |
| **Status** | ⬜ Pendente |

### T7.2 - Swagger UI
| ID | T7.2 |
|----|------|
| **Objetivo** | Verificar documentação interativa |
| **Pré-condição** | API iniciada |
| **Passos** | 1. Acessar http://localhost:8000/docs |
| **Resultado Esperado** | Interface Swagger com todos os endpoints |
| **Status** | ⬜ Pendente |

### T7.3 - Validação de Dados (Erro)
| ID | T7.3 |
|----|------|
| **Objetivo** | Verificar validação de tipos |
| **Pré-condição** | API rodando |
| **Passos** | 1. Via Swagger: `POST /orders` com `numero_pedido` como texto |
| **Resultado Esperado** | Erro 422 - Unprocessable Entity |
| **Status** | ⬜ Pendente |

### T7.4 - Item Não Encontrado (Erro)
| ID | T7.4 |
|----|------|
| **Objetivo** | Verificar tratamento de 404 |
| **Pré-condição** | API rodando |
| **Passos** | 1. Via Swagger: `GET /orders/CODIGO_INEXISTENTE` |
| **Resultado Esperado** | Erro 404 - Not Found |
| **Status** | ⬜ Pendente |

---

## 📊 Resumo de Testes

| Módulo | Total de Testes | Categoria |
|--------|-----------------|-----------|
| Ordens de Produção | 6 | CRUD + Chat |
| Peças | 6 | CRUD + Chat |
| Catálogo | 8 | CRUD + Estatísticas |
| Estoque | 8 | CRUD + Validações |
| Agente Chat | 6 | Interação + Contexto |
| Alertas | 2 | Análise |
| API REST | 4 | Integridade |
| **TOTAL** | **40** | |

---

## 📝 Template de Registro de Teste

```markdown
| Data | Testador | ID Teste | Resultado | Observações |
|------|----------|----------|-----------|-------------|
| DD/MM/AAAA | Nome | T1.1 | ✅ Passou / ❌ Falhou | Detalhes |
```

---

## 🐛 Template de Registro de Bug

```markdown
### Bug #XXX - Título do Problema

**Teste relacionado:** T1.1
**Severidade:** Alta / Média / Baixa
**Data:** DD/MM/AAAA

**Descrição:**
Descrição detalhada do problema encontrado.

**Passos para reproduzir:**
1. Passo 1
2. Passo 2
3. ...

**Comportamento esperado:**
O que deveria acontecer.

**Comportamento real:**
O que realmente aconteceu.

**Screenshots/Logs:**
[anexar se aplicável]

**Status:** Aberto / Em Análise / Resolvido
```

---

*Versão: 1.0 | Criado em: Janeiro 2026*
