.PHONY: install test verify build-console dry-run

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

export APP_ENV := test
export USE_IN_MEMORY_FIRESTORE := true
export GITHUB_WEBHOOK_SECRET := test-webhook-secret-12345

install: $(VENV)/bin/pytest

$(VENV)/bin/pytest: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test: install
	$(PYTHON) -m pytest tests/ -q

build-console:
	cd console-ui && npm ci && npm run build

dry-run: install
	PYTHONPATH=. $(PYTHON) scripts/dry_run_issue_1.py

verify: test build-console dry-run
