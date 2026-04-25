.ONESHELL:
MAKEFLAGS += --no-print-directory --quiet
SHELL := /bin/bash

.DEFAULT_GOAL := help
NOCOLOR='\033[0m'
YELLOW = '\033[33m'

help:
	@echo -e $(YELLOW) "make up:" $(NOCOLOR)
	@echo "     Start infra only (Cockroach, RabbitMQ, Redis). Use with the manual 4-terminal flow."
	@echo -e $(YELLOW) "make demo:" $(NOCOLOR)
	@echo "     Run the full stack (infra + 4 services) via docker compose. Single-command demo."
	@echo -e $(YELLOW) "make down:" $(NOCOLOR)
	@echo "     Tear everything down (both 'up' and 'demo' stacks)."
	@echo -e $(YELLOW) "make install:" $(NOCOLOR)
	@echo "     Install Python deps for all 4 services (manual flow only — demo handles its own)."


up:
	./dev_setup/up.sh

demo:
	docker compose up --build

down:
	-docker compose down -v --remove-orphans
	-./dev_setup/down.sh


install: 
	cd repos/payment_gateway && poetry install --with dev --no-root
	cd ../..
	cd repos/omnibus && poetry install --with dev --no-root
	cd ../..
	cd repos/investment-wallet && poetry install --with dev --no-root
	cd ../..
	cd repos/gateway && poetry install --with dev --no-root

