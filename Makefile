.ONESHELL:
MAKEFLAGS += --no-print-directory --quiet
SHELL := /bin/bash

.DEFAULT_GOAL := help
NOCOLOR='\033[0m'
YELLOW = '\033[33m'

help:
	@echo -e $(YELLOW) "make up:" $(NOCOLOR)
	@echo "     To run dependencies and start the project"
	@echo -e $(YELLOW) "make githooks_enable:" $(NOCOLOR)
	@echo "     to tear down the project"
	@echo -e $(YELLOW) "make demo:" $(NOCOLOR)
	@echo "     Run the full stack (Cockroach + RabbitMQ + 4 services) via docker compose"
	@echo -e $(YELLOW) "make demo-down:" $(NOCOLOR)
	@echo "     Tear down the dockerized demo stack"


up:
	./dev_setup/up.sh

down:
	./dev_setup/down.sh

demo:
	docker compose up --build

demo-down:
	docker compose down -v


install: 
	cd repos/payment_gateway && poetry install --with dev --no-root
	cd ../..
	cd repos/omnibus && poetry install --with dev --no-root
	cd ../..
	cd repos/investment-wallet && poetry install --with dev --no-root
	cd ../..
	cd repos/gateway && poetry install --with dev --no-root

