.PHONY: dev build stop reset logs test test-full lint install

dev:
	docker-compose up

dev-bg:
	docker-compose up -d

build:
	docker-compose build

stop:
	docker-compose down

reset:
	docker-compose down -v
	rm -rf data/lucy.db data/reports/

logs:
	docker-compose logs -f --tail=100

logs-backend:
	docker-compose logs -f backend

logs-worker:
	docker-compose logs -f celery_worker

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

test:
	cd backend && python -m pytest tests/test_auth.py tests/test_agents.py tests/test_library.py tests/test_metrics.py -v --tb=short

test-full:
	cd backend && python -m pytest tests/ -v --tb=short

lint:
	python -m flake8 backend --select=E9,F63,F7,F82 --exclude=backend/modules,backend/core/library/registry.py
	cd frontend && npm run lint

agent-build:
	cd agent && pyinstaller --onefile --name lucy_agent main.py

shell-backend:
	docker-compose exec backend /bin/bash

shell-redis:
	docker-compose exec redis redis-cli
