.PHONY: all build up down logs restart test clean setup

# Detect Docker Compose command (v2: "docker compose", v1: "docker-compose")
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || (command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || echo ""))

# Detect Python command (python3 preferred, fallback to python)
PYTHON := $(shell command -v python3 >/dev/null 2>&1 && echo "python3" || (command -v python >/dev/null 2>&1 && echo "python" || echo ""))

# Guard checks for required tools
$(if $(COMPOSE),,$(error Docker Compose not found; please install 'docker compose' or 'docker-compose'))
$(if $(PYTHON),,$(error Python not found; please install python3))

all: build up

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

restart:
	$(COMPOSE) restart

test:
	PYTHONPATH=bot $(PYTHON) -m pytest tests/ -v

clean:
	$(COMPOSE) down --volumes --rmi local

setup:
	@./scripts/setup-credentials.sh
