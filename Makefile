SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

install:  ## Install the stack
	poetry install --extras "pandas"
.PHONY: install

test-integration: ## Do a simple integration test
	poetry run python ./bin/markdowncode.py ./docs/tutorial.md | BASE_URL="http://localhost:8000" PYTHONPATH="avatars/" poetry run python --
.PHONY: test-integration

DOC_OUTPUT_DIR ?= doc/build/html# will read from DOC_OUTPUT_DIR environment variable. Uses in github actions
DOC_SOURCE_DIR := doc/source

doc: doc-build  ## Build and open the docs
	poetry run python -m webbrowser -t $(DOC_OUTPUT_DIR)/index.html
.PHONY: doc

doc-build:  # Build the docs
	poetry run pandoc --from=markdown --to=rst --output=$(DOC_SOURCE_DIR)/tutorial.rst docs/tutorial.md
	poetry run sphinx-build -b html $(DOC_SOURCE_DIR) $(DOC_OUTPUT_DIR)
	poetry run python doc/bin/modify_class_name.py $(DOC_OUTPUT_DIR)
.PHONY: doc-build

lci: lint-fix lint test-integration doc-build
.PHONY: lci

lint-fix:
	poetry run black avatars/ bin doc/source
	poetry run blacken-docs docs/tutorial.md
	poetry run isort avatars/ bin doc/source
.PHONY: lint-fix

lint:
	poetry run bandit -r avatars
.PHONY: lint

.DEFAULT_GOAL := help
help: Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} /^[\/\.a-zA-Z1-9_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
