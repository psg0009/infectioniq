# InfectionIQ

**AI-Powered Surgical Infection Prevention**

*"We predict surgical infections before they happen by tracking contamination pathways in real-time."*

## Overview

InfectionIQ is a computer vision and machine learning system designed to reduce surgical site infections by:

1. **PredictoHygiene**: Predicting infection risk BEFORE surgery begins
2. **TouchTrace**: Tracking contamination pathways DURING surgery

## Features

- 🎥 Vision-only hand hygiene monitoring (no badges required)
- 🖐️ Real-time hand tracking and gesture recognition
- 🚨 Contamination detection and alerts
- 📊 Risk prediction using ML ensemble models
- 📈 Compliance analytics and reporting
- 🏥 EMR/EHR integration ready

## Architecture

```
infectioniq/
├── backend/          # FastAPI backend server
├── cv_module/        # Computer vision pipeline
├── frontend/         # React dashboard
├── edge/             # Edge deployment configs
├── docker/           # Docker configurations
├── scripts/          # Utility scripts
└── docs/             # Documentation
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15
- Redis 7

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/infectioniq.git
cd infectioniq

# Run setup script
./scripts/setup_dev.sh

# Start all services
docker-compose up -d

# Access dashboard
open http://localhost:3000
```

### Manual Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### CV Module

```bash
cd cv_module
pip install -r requirements.txt
python src/main.py --camera 0
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/infectioniq
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
```

## API Documentation

Once running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, SQLAlchemy, Pydantic |
| CV Pipeline | OpenCV, MediaPipe, YOLOv8 |
| ML | XGBoost, PyTorch, scikit-learn |
| Frontend | React, TypeScript, Tailwind CSS |
| Database | PostgreSQL, TimescaleDB, Redis |
| Deployment | Docker, NVIDIA Jetson |

## License

Proprietary - All rights reserved

## Contact

For questions or pilot partnerships, contact: team@infectioniq.com
