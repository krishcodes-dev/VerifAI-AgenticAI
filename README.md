# VerifAI - Agentic AI Fraud Detection System

Real-time autonomous fraud detection and prevention using ML + WhatsApp integration.

## Tech Stack
- **Backend:** FastAPI, Python 3.11+
- **ML:** XGBoost, scikit-learn, pandas
- **Database:** PostgreSQL, Redis
- **Integration:** WhatsApp Business API
- **Deployment:** Docker, Heroku/Railway

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### Installation
```bash
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Database & Migrations
Ensure PostgreSQL is running locally. Then apply the database schema migrations:
```bash
alembic upgrade head
```
*(To generate a new migration after changing models: `alembic revision --autogenerate -m "description"`)*

### Train Model
```bash
python app/ml/model_training.py
```

### Run Server
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Server runs at: http://localhost:8000

### API Documentation
Once running, visit: http://localhost:8000/docs

## Project Structure
```text
VerifAI/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── models/
│   ├── services/
│   ├── api/
│   └── ml/
├── tests/
├── data/
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## Features
✅ Real-time transaction monitoring

✅ ML-based fraud scoring (94% accuracy)

✅ Autonomous decision making

✅ WhatsApp alerts & verification

✅ Continuous learning from feedback

## Agentic Workflow
PERCEIVE - Collect transaction data

REASON - Calculate fraud risk

DECIDE - Make autonomous decision

ACT - Execute actions (block, alert, verify)

LEARN - Improve from feedback
