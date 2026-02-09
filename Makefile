.PHONY: api worker verify

api:
	PYTHONPATH=. uvicorn src.main:app --reload --port 8000

worker:
	PYTHONPATH=. python src/workers/document_worker.py

verify:
	PYTHONPATH=. python scripts/verify_infra.py
