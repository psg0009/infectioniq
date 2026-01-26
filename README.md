# InfectionIQ

**AI-Powered Surgical Infection Prevention**

*"We predict surgical infections before they happen by tracking contamination pathways in real-time."*

## Overview

InfectionIQ is a computer vision and machine learning system designed to reduce surgical site infections by:

1. **PredictoHygiene**: Predicting infection risk BEFORE surgery begins
2. **TouchTrace**: Tracking contamination pathways DURING surgery

## Features

- Vision-only hand hygiene monitoring (no badges required)
- Real-time hand tracking and gesture recognition
- Contamination detection and alerts
- Risk prediction using ML ensemble models
- Compliance analytics and reporting
- EMR/EHR integration ready

## Architecture

```
infectioniq/
├── backend/          # FastAPI backend server
│   ├── app/          # Main application code
│   │   ├── api/      # API routes (v1)
│   │   ├── core/     # Database & Redis setup
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   └── services/ # Business logic
│   └── ml/           # ML models and risk predictor
├── cv_module/        # Computer vision pipeline
│   ├── models/       # Pre-trained models (YOLOv8, MediaPipe)
│   └── src/          # CV source code
└── frontend/         # React dashboard
    └── src/
        ├── components/  # React components
        ├── pages/       # Page components
        ├── stores/      # Zustand state management
        └── types/       # TypeScript types
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Git**

---

## Quick Start

### 1. Backend Setup

```bash
# Navigate to backend folder
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
venv\Scripts\activate
# Windows (CMD):
venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Seed database with test data
python seed_data.py

# Run the server
python -m app.main
```

**Backend runs on:** http://localhost:8000

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

### 2. Frontend Setup

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

**Frontend runs on:** http://localhost:3000

---

### 3. CV Module Setup (Optional - requires camera)

```bash
# Navigate to cv_module folder
cd cv_module

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with default camera
python -m src.main --camera 0
```

**CV Module Options:**
| Flag | Description |
|------|-------------|
| `--camera 0` | Camera source index (default: 0) |
| `--backend URL` | Backend API URL (default: http://localhost:8000) |
| `--case-id ID` | Surgical case ID |
| `--or OR-1` | Operating room number |

---

## Running All Services

Open **3 separate terminals**:

| Terminal | Command |
|----------|---------|
| 1 - Backend | `cd backend && venv\Scripts\activate && python -m app.main` |
| 2 - Frontend | `cd frontend && npm run dev` |
| 3 - CV Module | `cd cv_module && venv\Scripts\activate && python -m src.main --camera 0` |

---

## Environment Configuration

Create a `.env` file in the `backend/` folder (optional for development):

```env
# Application
APP_NAME=InfectionIQ
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database (SQLite - auto-created, no setup required)
DATABASE_URL=sqlite:///./infectioniq.db

# Redis (uses fakeredis by default - no Redis install needed)
USE_FAKEREDIS=true

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=change-me-in-production
JWT_SECRET_KEY=change-me-in-production

# CORS Origins
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

---

## API Endpoints

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Basic health check |
| GET | `/health` | Detailed health status |

### API v1 Routes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/cases` | Surgical cases management |
| GET/POST | `/api/v1/staff` | Staff management |
| GET/POST | `/api/v1/compliance` | Compliance tracking |
| GET/POST | `/api/v1/alerts` | Alert management |
| GET/POST | `/api/v1/dispensers` | Sanitizer dispensers |
| GET/POST | `/api/v1/analytics` | Analytics and reporting |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws/` | Real-time event streaming |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI, SQLAlchemy, Pydantic |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Cache** | Redis / FakeRedis |
| **CV Pipeline** | OpenCV, MediaPipe, YOLOv8 |
| **ML** | XGBoost, LightGBM, CatBoost, ONNX Runtime |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **State** | Zustand |
| **Charts** | Recharts |

---

## Troubleshooting

### Backend won't start
```bash
# Make sure virtual environment is activated
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Frontend port already in use
```bash
npx kill-port 3000
```

### CV Module camera not found
```bash
# Try different camera index
python -m src.main --camera 1
```

### Database errors
```bash
# Delete and recreate database
del backend\infectioniq.db
python -m app.main
```

---

## License

Proprietary - All rights reserved

## Contact

For questions or pilot partnerships, contact: team@infectioniq.com
