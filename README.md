# SEVA AI - Smart Citizen Services Portal

SEVA AI is an AI-empowered digital governance platform designed to simplify citizen services, document vault management, and application workflows.

## Architecture

- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, PyJWT, Passlib (Bcrypt)
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Infrastructure**: Docker & Docker Compose

## Getting Started

### Prerequisites
- Docker & Docker Compose (or local PostgreSQL 16 & Node.js 20+)
- Python 3.11+

### Local Setup (Backend)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

### Local Setup (Frontend)
```bash
cd frontend
npm install
npm run dev
```

### Docker Setup
```bash
docker-compose up --build
```
