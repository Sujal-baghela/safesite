.PHONY: help dev backend frontend worker migrate test lint clean

help:
	@echo "SafeSite development commands:"
	@echo "  make dev        Start all services (docker-compose)"
	@echo "  make backend    Start FastAPI server only"
	@echo "  make frontend   Start Next.js dev server"
	@echo "  make worker     Start ARQ background worker"
	@echo "  make migrate    Run Alembic migrations"
	@echo "  make test       Run backend tests"
	@echo "  make lint       Lint backend with Ruff"
	@echo "  make clean      Stop and remove containers"

dev:
	docker-compose up --build

infra:
	docker-compose up -d postgres redis

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

worker:
	cd backend && uv run arq app.tasks.worker.WorkerSettings

migrate:
	cd backend && uv run alembic upgrade head

migrate-create:
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

test:
	cd backend && uv run pytest -v

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

clean:
	docker-compose down -v
