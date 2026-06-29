# Pitbox — Setup

## Pré-requisitos
- Python 3.11+
- Node.js 18+
- PostgreSQL (local ou Railway)

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env         # editar com suas credenciais
uvicorn app.main:app --reload
```

API disponível em http://localhost:8000
Docs em http://localhost:8000/docs

## Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

App disponível em http://localhost:5173

## Deploy Railway

1. Criar conta em railway.app
2. Novo projeto → Deploy from GitHub
3. Adicionar variáveis de ambiente (.env)
4. Adicionar PostgreSQL plugin
5. Deploy automático a cada push
