# ============================================================
# eVera v1.0 — Makefile
# ============================================================

.PHONY: help build up down logs test bench shell clean

COMPOSE = docker compose
IMAGE   = evera:latest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build Docker image
	$(COMPOSE) build

up: ## Start all services (detached)
	$(COMPOSE) up -d
	@echo "\neVera is running at http://localhost:$${VERA_SERVER_PORT:-8000}"

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail eVera logs
	$(COMPOSE) logs -f vera

restart: ## Restart eVera
	$(COMPOSE) restart vera

status: ## Show service status
	$(COMPOSE) ps

test: ## Run tests in container
	$(COMPOSE) run --rm vera test

bench: ## Run benchmarks in container
	$(COMPOSE) run --rm vera benchmark

shell: ## Open shell in container
	$(COMPOSE) exec vera /bin/bash || $(COMPOSE) run --rm vera shell

clean: ## Remove containers, volumes, and images
	$(COMPOSE) down -v --rmi local
	@echo "Cleaned up!"

pull-model: ## Pull Ollama model
	$(COMPOSE) exec ollama ollama pull $${VERA_LLM_OLLAMA_MODEL:-llama3.2}

prod-up: ## Start in production mode
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down: ## Stop production
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml down

staging-up: ## Start in staging mode (zone testing)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.staging.yml up -d
	@echo "\neVera staging at http://localhost:$${VERA_SERVER_PORT:-8001}"

staging-down: ## Stop staging
	$(COMPOSE) -f docker-compose.yml -f docker-compose.staging.yml down

staging-test: ## Run zone E2E tests against staging
	python test_zones_e2e.py

health: ## Check service health
	@curl -sf http://localhost:$${VERA_SERVER_PORT:-8000}/health && echo "eVera: OK" || echo "eVera: DOWN"
	@curl -sf http://localhost:11434/api/tags > /dev/null && echo "Ollama: OK" || echo "Ollama: DOWN"
