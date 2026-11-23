# SafeSite 🦺

**AI-powered PPE violation detection for construction sites.**

Detects missing helmets, vests, gloves, and boots from camera feeds or uploaded images/videos using YOLO11. Built as a fully open-source, self-hostable B2B SaaS.

![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.12-blue) ![Next.js](https://img.shields.io/badge/next.js-15-black)

---

## Features

- 🎥 **Image & video PPE detection** — upload a photo or video, get violation detections with bounding boxes
- 📊 **Dashboard** — live violation feed, filterable log, analytics charts
- 🔔 **Alerts** — WhatsApp and email notifications on violation (Phase 4)
- 📄 **PDF reports** — weekly compliance summary per site (Phase 4)
- 🔐 **RBAC** — Super Admin, Company Admin, Site Manager, Viewer roles
- 🐳 **Docker** — one command to run everything locally

---

## Quickstart

### Prerequisites
- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- [Node.js 20+](https://nodejs.org/)
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/safesite.git
cd safesite

# Copy env templates
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# Set at minimum:
# backend/.env  → JWT_SECRET=<any-long-random-string>
# frontend/.env.local → NEXTAUTH_SECRET=<any-long-random-string>
```

### 2. Start infrastructure

```bash
docker-compose up -d postgres redis
```

### 3. Run migrations

```bash
cd backend
uv sync
uv run alembic upgrade head
```

### 4. Start backend

```bash
# In /backend
uv run uvicorn app.main:app --reload
# API running at http://localhost:8000
# Docs at http://localhost:8000/api/docs
```

### 5. Start frontend

```bash
# In /frontend
npm install
npm run dev
# App running at http://localhost:3000
```

### 6. Start background worker (for video processing)

```bash
# In /backend (separate terminal)
uv run arq app.tasks.worker.WorkerSettings
```

### Or: run everything with Docker

```bash
docker-compose up --build
```

---

## Get the ML model

```bash
# Option A: Download base YOLO11 weights (no account needed)
python ml/models/download_weights.py --pretrained-only

# Option B: Download PPE-trained weights from Roboflow
python ml/models/download_weights.py --api-key YOUR_ROBOFLOW_KEY

# Save to: ml/models/ppe_yolo11.pt
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new account |
| POST | `/api/v1/auth/login` | Login, get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Invalidate session |
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/detect/image` | Upload image → detection |
| POST | `/api/v1/detect/video` | Upload video → async job |
| GET | `/api/v1/violations` | List violations (filtered) |
| GET | `/api/v1/violations/{id}` | Single violation detail |
| PATCH | `/api/v1/violations/{id}/resolve` | Resolve / re-open |
| GET | `/api/v1/jobs/{job_id}` | Poll video job status |

---

## Project structure

```
safesite/
├── frontend/          Next.js 15, TanStack Query, shadcn/ui
├── backend/           FastAPI, SQLAlchemy async, ARQ workers
│   ├── app/
│   │   ├── api/v1/   REST endpoints
│   │   ├── core/     config, security, cache, database, storage
│   │   ├── models/   SQLAlchemy ORM models
│   │   ├── schemas/  Pydantic v2 request/response schemas
│   │   ├── crud/     database operations
│   │   └── tasks/    ARQ background workers
│   ├── alembic/      DB migrations
│   └── tests/        pytest test suite
└── ml/               YOLO11 PPE detector
    ├── inference/    detector, video processor, utils
    └── training/     fine-tuning script
```

---

## Tech stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15, Tailwind CSS v4, shadcn/ui, TanStack Query v5 |
| Backend | FastAPI, SQLAlchemy 2 async, Alembic, ARQ |
| CV / ML | YOLO11 (Ultralytics), PyTorch, OpenCV, Supervision |
| Database | PostgreSQL (Neon in prod) |
| Cache / Queue | Redis (Upstash in prod) |
| Storage | Cloudflare R2 |
| Auth | next-auth v5, JWT (15 min access / 7 day refresh) |

---

## Development commands

```bash
make dev          # docker-compose up --build
make infra        # start postgres + redis only
make backend      # uvicorn with --reload
make frontend     # next dev
make worker       # arq worker
make migrate      # alembic upgrade head
make test         # pytest
make lint         # ruff check + format check
```

---

## Roadmap

- [x] Phase 1 — Foundation (auth, DB, Redis, roles)
- [x] Phase 2 — CV Engine (YOLO11, image/video detection, R2 storage)
- [ ] Phase 3 — Dashboard (live feed, analytics, violation log)
- [ ] Phase 4 — Alerts & Reports (WhatsApp, email, PDF)
- [ ] Phase 5 — Security hardening (rate limits, SAST, audit log)

---

## License

MIT — see [LICENSE](LICENSE)

---

## Contributing

PRs welcome. Please follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`).
