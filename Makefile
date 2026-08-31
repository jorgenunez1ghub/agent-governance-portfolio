PYTHON ?= .venv/bin/python
PYCACHE_DIR ?= /private/tmp/agent-governance-mvp-pycache

.PHONY: verify test eval outcome-evidence-config compile shellcheck

verify: test eval outcome-evidence-config compile shellcheck

test:
	$(PYTHON) -m pytest -q -p no:cacheprovider

eval:
	$(PYTHON) -m evals.run_policy_evals

outcome-evidence-config:
	$(PYTHON) -m evals.outcome_benchmark validate-config

compile:
	PYTHONPYCACHEPREFIX=$(PYCACHE_DIR) $(PYTHON) -m compileall -q app evals tests

shellcheck:
	bash -n demo_flow.sh
