PYTHON ?= .venv/bin/python
.PHONY: local-check local-render
local-check:
	$(PYTHON) -m localdev.checks
local-render:
	kubectl kustomize environments/local/platform
	kubectl kustomize environments/local/observability
	kubectl kustomize environments/local/apps
