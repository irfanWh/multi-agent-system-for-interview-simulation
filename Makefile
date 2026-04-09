# Makefile
.PHONY: up down logs shell-backend migrate seed

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

shell-backend:
	docker compose exec backend bash

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python scripts/seed.py
