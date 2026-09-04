# Smart Market Watchlist

> **Code, by Groww 2026** – engineering challenge submission.

A watchlist that does not merely show users what their stocks are doing, but tells them **what has meaningfully changed since they last checked**, prioritises the changes that deserve attention, and explains why.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + JavaScript + Vite |
| Backend | Python + FastAPI + Pydantic |
| ORM / Migrations | SQLAlchemy + Alembic |
| Database | PostgreSQL 16 |
| Local DB runtime | Docker Compose |

---

## Project Structure

```
smart-market-watchlist/
├── frontend/        React + Vite application
├── backend/         FastAPI application
├── docs/            Architecture and design documentation
├── docker-compose.yml   Local PostgreSQL
├── .gitignore
└── README.md
```

---

## Local Setup

### Prerequisites

- **Node.js** ≥ 18 and **npm** ≥ 9
- **Python** ≥ 3.11
- **Docker** and **Docker Compose**

---

### 1 · Start PostgreSQL

```bash
docker compose up -d
```

The database will be available at `localhost:5432`.  
Credentials are defined in `docker-compose.yml` (development only – do not use in production).

---

### 2 · Start the Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and review environment variables
cp .env.example .env

# Start the development server
uvicorn app.main:app --reload --port 8000
```

The API will be available at <http://localhost:8000>.  
Interactive API docs: <http://localhost:8000/docs>  
Health check: <http://localhost:8000/api/v1/health>

---

### 3 · Start the Frontend

```bash
cd frontend
npm install       # skip if already done
npm run dev
```

The application will be available at <http://localhost:5173>.

---

## Current Status

This is the **initial project skeleton**.

| Component | Status |
|---|---|
| Frontend (React + Vite) | ✅ Runnable skeleton |
| Backend (FastAPI) | ✅ Health-check endpoint |
| PostgreSQL (Docker) | ✅ Runs locally |
| Watchlist features | ⬜ Not yet implemented |
| Market data integration | ⬜ Not yet implemented |
| Change detection | ⬜ Not yet implemented |
| User authentication | ⬜ Not yet implemented |

---

## Documentation

- [Architecture overview](docs/architecture.md)

---

## Licence

Submission for Code, by Groww 2026. All rights reserved.
