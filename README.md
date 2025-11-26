# Sistema de Monitoramento de Produção

Este projeto é uma automação local para acompanhamento de produção, utilizando FastAPI, Streamlit e Supabase.

## Estrutura

- `src/api.py`: Backend (FastAPI)
- `src/app_streamlit.py`: Frontend (Streamlit)
- `src/database.py`: Conexão com Supabase
- `src/models.py`: Modelos de dados

## Configuração

1.  Crie um ambiente virtual (opcional mas recomendado):
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

2.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

3.  Configure as variáveis de ambiente:
    - Renomeie `.env.example` para `.env`
    - Adicione suas credenciais do Supabase (`SUPABASE_URL` e `SUPABASE_KEY`)

## Como Rodar

### Método Recomendado (usando scripts)
Você precisará de dois terminais abertos na pasta do projeto.

**Terminal 1 (API):**
```powershell
.\start_api.ps1
```

**Terminal 2 (Frontend):**
```powershell
.\start_streamlit.ps1
```

### Método Manual
Se preferir rodar manualmente, use:

**Terminal 1 (API):**
```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload
```

**Terminal 2 (Frontend):**
```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app_streamlit.py
```

## Uso

1.  Abra o Streamlit no navegador (geralmente `http://localhost:8501`).
2.  Faça upload de um PDF de pedido (qualquer PDF serve para a demo, os dados são simulados).
3.  Confirme a criação da Ordem no chat.
4.  Confirme a criação das Peças.
5.  Use o botão "Verificar Alertas" na barra lateral para testar a lógica de análise.
