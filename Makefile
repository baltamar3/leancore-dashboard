.PHONY: install lint test test-unit test-integration run-api run-consumer up down demo

install:
	pip install -e ".[dev]"

lint:
	ruff check .

test: test-unit test-integration

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

run-api:
	uvicorn src.api.app:app --reload --port 8000

run-consumer:
	python -m src.consumer.main

up:
	docker compose up --build

down:
	docker compose down -v

demo:
	bash scripts/demo.sh
