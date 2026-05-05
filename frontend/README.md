# AIOps SRE Streamlit Frontend

This Streamlit application provides a production-ready UI for the AIOps SRE assistant. It connects to the FastAPI backend to list incidents, inspect logs and metrics, chat with the AI assistant, and approve solutions for Auto-Learning.

## ✅ Prerequisites

- Python 3.11+
- Running backend API (`http://localhost:8000/api/v1` by default)

## 🚀 Quick Start

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `BACKEND_URL` | FastAPI base URL | `http://localhost:8000/api/v1` |
| `REQUEST_TIMEOUT` | HTTP timeout (seconds) | `10` |
| `CACHE_TTL_SECONDS` | Cache TTL (seconds) | `30` |
| `MAX_LOG_LINES` | Max logs displayed | `100` |
| `MAX_METRICS_POINTS` | Max metrics displayed | `100` |

## 🧭 Pages

- **Dashboard**: global incident overview and filters.
- **Incident Analysis**: overview context, logs, metrics, AI solution, chat, approvals.
- **Settings**: diagnostics and cache management.

## 🛠️ Notes

- Use the sidebar to filter incidents by severity, status, or search terms.
- Approvals trigger `PUT /incidents/{id}/resolve` to persist Auto-Learning.
