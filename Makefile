.PHONY: all build up down logs restart test clean

all: build up

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

clean:
	docker compose down --volumes --rmi local
