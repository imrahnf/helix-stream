# Variables
COMPOSE_FILE := infra/docker/docker-compose.yml
ENV_FILE := .env

.PHONY: help clean local hybrid-mac hybrid-win logs stop start-local start-mac start-win restart-local restart-mac restart-win

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

clean: ## [Maintenance] Kill all containers and clear network orphans
	docker compose -f $(COMPOSE_FILE) --profile full --profile macos down --remove-orphans

# --- BUILD & START (Use these when you change code) ---

local: ## [Build] Local Dev Mode (All services on Mac)
	TITAN_IP= docker compose -f $(COMPOSE_FILE) --profile full up -d --build

hybrid-mac: ## [Build] Hybrid Mode - Control Plane (Mac)
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) --profile macos up -d --build --force-recreate

hybrid-win: ## [Build] Hybrid Mode - Compute Node (Windows)
	docker compose -f $(COMPOSE_FILE) --profile windows up -d --build --force-recreate

# --- START ONLY (No Rebuild - Fast Startup) ---

start-local: ## [Fast Start] Start Local Full Stack
	TITAN_IP= docker compose -f $(COMPOSE_FILE) --profile full up -d

start-mac: ## [Fast Start] Start Mac Control Plane
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) --profile macos up -d

start-win: ## [Fast Start] Start Windows Compute Node
	docker compose -f $(COMPOSE_FILE) --profile windows up -d

# --- RESTART (Stop -> Start, No Rebuild) ---

restart-local: ## [Restart] Reset Local Full Stack
	$(MAKE) stop
	$(MAKE) start-local

restart-mac: ## [Restart] Reset Mac Control Plane
	$(MAKE) stop
	$(MAKE) start-mac

restart-win: ## [Restart] Reset Windows Compute Node
	$(MAKE) stop
	$(MAKE) start-win

# --- UTILS ---

logs: ## [View] View logs for the gateway
	docker logs -f helix_gateway

stop: ## [Stop] Stop and remove all running containers
	docker compose -f $(COMPOSE_FILE) down