# =============================================================================
# SyncRivo Email Service — Makefile
# Shortcuts for common Docker Compose workflows
# =============================================================================

.PHONY: up down build logs restart shell-api shell-mongo ps clean help

## Start all services (detached, with build)
up:
	docker compose up -d --build

## Start all services and stream logs
up-logs:
	docker compose up --build

## Stop and remove containers (keeps volumes)
down:
	docker compose down

## Stop containers and DELETE all data volumes
down-clean:
	@echo "⚠️  This will DELETE all MongoDB data. Press Ctrl+C to abort..."
	@sleep 5
	docker compose down -v

## Build images without starting
build:
	docker compose build

## Build without using Docker cache
build-fresh:
	docker compose build --no-cache

## Stream logs from all services
logs:
	docker compose logs -f

## Stream logs from a specific service: make logs-api / logs-frontend / logs-mongo
logs-api:
	docker compose logs -f api

logs-frontend:
	docker compose logs -f frontend

logs-mongo:
	docker compose logs -f mongo

## Restart a specific service
restart-api:
	docker compose restart api

restart-frontend:
	docker compose restart frontend

## Open a bash shell in the API container
shell-api:
	docker compose exec api bash

## Open mongosh in the mongo container
shell-mongo:
	docker compose exec mongo mongosh email_service

## List running containers and their status
ps:
	docker compose ps

## Remove stopped containers, unused images, and build cache
clean:
	docker compose down
	docker system prune -f

## Show this help
help:
	@echo ""
	@echo "SyncRivo Email Service — Docker Commands"
	@echo "────────────────────────────────────────"
	@echo "  make up            Start all services (build + detached)"
	@echo "  make up-logs       Start all services with live log stream"
	@echo "  make down          Stop all containers"
	@echo "  make down-clean    Stop + delete all data volumes"
	@echo "  make build         Build images only"
	@echo "  make build-fresh   Build images (no cache)"
	@echo "  make logs          Stream all logs"
	@echo "  make logs-api      Stream API logs only"
	@echo "  make logs-frontend Stream frontend logs only"
	@echo "  make shell-api     Open bash in API container"
	@echo "  make shell-mongo   Open mongosh in mongo container"
	@echo "  make ps            Show container status"
	@echo "  make clean         Remove containers + prune Docker"
	@echo ""
