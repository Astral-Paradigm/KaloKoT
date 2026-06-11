.PHONY: start stop restart health backup restore install uninstall

HOST ?= 127.0.0.1
PORT ?= 7860

start:  ## Start Justice_system (dev mode)
	./scripts/start.sh dev

stop:   ## Stop Justice_system
	./scripts/stop.sh

restart: stop start  ## Restart

prod:   ## Start in production mode
	./scripts/start.sh prod

share:  ## Start with Gradio public link
	./scripts/start.sh share

health: ## Check server status
	./scripts/healthcheck.sh

backup: ## Backup project (source + legal + config)
	./scripts/backup.sh

restore: ## Restore from backup
	./scripts/restore.sh $(FILE)

docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start with Docker
	docker compose up -d

docker-down: ## Stop Docker
	docker compose down

install: ## Install systemd service
	sudo cp systemd/justice.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable justice.service
	sudo systemctl start justice.service
	@echo "Justice service installed and started."
	@echo "Status: sudo systemctl status justice.service"

uninstall: ## Remove systemd service
	sudo systemctl stop justice.service 2>/dev/null || true
	sudo systemctl disable justice.service 2>/dev/null || true
	sudo rm -f /etc/systemd/system/justice.service
	sudo systemctl daemon-reload
	@echo "Justice service uninstalled."

logs:   ## Tail server logs
	tail -f logs/justice.log 2>/dev/null || echo "No log file found"

venv:   ## Create virtual environment
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

help:   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
