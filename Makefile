.PHONY: setup check agent-evals verify-feature

PYTHON ?= python
FEATURE ?=

setup:
	$(PYTHON) scripts/bootstrap.py

check:
	$(PYTHON) scripts/verify.py --offline

agent-evals:
	$(PYTHON) scripts/verify.py --agent-evals

verify-feature:
	@test -n "$(FEATURE)" || (echo "Usage: make verify-feature FEATURE=feat-..." && exit 2)
	$(PYTHON) scripts/verify_feature.py $(FEATURE)
