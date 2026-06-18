.PHONY: up down build logs ps shell-backend migrate test lint

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

shell-backend:
	docker compose exec backend bash

migrate:
	docker compose exec backend alembic upgrade head

migration:
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

test:
	docker compose exec backend pytest -v

lint:
	docker compose exec backend mypy app/

pull-models:
	docker compose exec ollama ollama pull qwen3:8b
	docker compose exec ollama ollama pull bge-m3

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

restart-backend:
	docker compose restart backend

health:
	curl -s http://localhost/health | python -m json.tool
