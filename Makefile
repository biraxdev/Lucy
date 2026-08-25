.PHONY: dev build stop reset logs test install

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
	cd backend && python -m pytest tests/ -v --tb=short

lint:
	cd backend && flake8 . --max-line-length=120 --exclude=__pycache__
	cd frontend && npx eslint src/ --ext .ts,.tsx

agent-build:
	cd agent && pyinstaller --onefile --name lucy_agent main.py

shell-backend:
	docker-compose exec backend /bin/bash

shell-redis:
	docker-compose exec redis redis-cli
