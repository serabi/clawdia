.PHONY: build up down logs restart test

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

test:
	python -m pytest tests/ -v
