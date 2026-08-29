.PHONY: install test verify build-console dry-run diff test-bounty

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

BOUNTY_GATE := tests/tier1_feature/test_f11_fleet_console.py tests/tier1_feature/test_f13_bounty_rehearsal.py tests/tier1_feature/test_f14_submission_packaging.py

export APP_ENV := test
export USE_IN_MEMORY_FIRESTORE := true
export GITHUB_WEBHOOK_SECRET := test-webhook-secret-12345

install: $(VENV)/bin/pytest

$(VENV)/bin/pytest: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test-bounty: install
	$(PYTHON) -m pytest $(BOUNTY_GATE) -q

test: $(VENV)/bin/pytest
	$(PYTHON) -m pytest tests/ -q

build-console:
	cd console-ui && npm ci && npm run build

dry-run: install
	PYTHONPATH=. $(PYTHON) scripts/dry_run_issue_1.py

diff:
	@git diff --stat master...HEAD

verify: test build-console dry-run
