SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

install:  ## Install the stack
	poetry install --sync
.PHONY: install

release-and-push:
	poetry run python release.py --bump-type patch
.PHONY: release-and-push

##@ Tests


test: typecheck test-integration  ## Run all the tests
.PHONY: test

typecheck:  ## Run the type checker
	poetry run mypy avatars --show-error-codes --pretty
.PHONY: typecheck

test-integration: ## Do a simple integration test
	poetry run python ./bin/markdowncode.py ./docs/tutorial.md | BASE_URL="http://localhost:8000" PYTHONPATH="avatars/" poetry run python --
.PHONY: test-integration

lci: generate-py lint-fix lint test-integration doc-build pip-requirements ## Apply the whole integration pipeline
.PHONY: lci

lint-fix: ## Fix linting
	poetry run black avatars/ bin doc/source notebooks/
	poetry run blacken-docs docs/tutorial.md
	poetry run isort avatars/ bin doc/source
	poetry run jupyter nbconvert --clear-output --inplace notebooks/*.ipynb
.PHONY: lint-fix

lint: ## Lint source files
	poetry run bandit -r avatars -c bandit.yaml
	poetry run flake8 .
.PHONY: lint


##@ Doc


DOC_OUTPUT_DIR ?= doc/build/html# will read from DOC_OUTPUT_DIR environment variable. Uses in github actions
DOC_SOURCE_DIR := doc/source

doc: doc-build  ## Build and open the docs
	python3 -m webbrowser -t $(DOC_OUTPUT_DIR)/index.html
.PHONY: doc

doc-build:  ## Build the docs
	rm -rf $(DOC_OUTPUT_DIR)
	poetry run pandoc --from=markdown --to=rst --output=$(DOC_SOURCE_DIR)/tutorial.rst docs/tutorial.md
	poetry run pandoc --from=markdown --to=rst --output=$(DOC_SOURCE_DIR)/changelog.rst CHANGELOG.md
	poetry run sphinx-build -b html $(DOC_SOURCE_DIR) $(DOC_OUTPUT_DIR)
	poetry run python doc/bin/modify_class_name.py $(DOC_OUTPUT_DIR)
.PHONY: doc-build


##@ Tutorial

TUTORIAL_REQUIREMENTS := requirements-tutorial.txt
VENV_NAME := notebooks/env


install-tutorial: ## Install the packages used for the tutorials
	poetry install --with tutorial --sync
.PHONY: install-tutorial


pip-requirements: ## Export the packages for the tutorials as a pip requirements.txt file
	poetry export -f requirements.txt -o  $(TUTORIAL_REQUIREMENTS) --with tutorial  --with main --without dev --without-hashes
.PHONY: pip-requirements


pip-install-tutorial: ## Install the dependecies of the tutorial via pip
	python3.9 -m venv $(VENV_NAME)
	"$(abspath $(VENV_NAME))/bin/pip3" install -r $(TUTORIAL_REQUIREMENTS)
	"$(abspath $(VENV_NAME))/bin/pip3" install . ## Installing the avatars package
.PHONY: pip-install-tutorial


notebook: pip-install-tutorial ## Start the tutorial notebooks
	PATH="file:///$(abspath $(VENV_NAME))/bin":$$PATH VIRTUAL_ENV="file:///$(abspath $(VENV_NAME))/bin" AVATAR_BASE_URL="http://localhost:8000" AVATAR_USERNAME="user_integration" AVATAR_PASSWORD="password_integration" jupyter notebook notebooks
.PHONY: notebook


generate-py:  ## Generate .py files from notebooks
	poetry run jupytext notebooks/*.ipynb  --from ipynb --to py
.PHONY: generate-py


test-tutorial: generate-py ## Verify that all tutorials run without errors
	echo "You must install the pip venv first. Run make pip-install-tutorial."

	SYSTEM=$$(uname -s)
	if [ $$SYSTEM = "Darwin" ]; then XARGS=gxargs; else XARGS=xargs; fi

	ls notebooks/Tutorial*.py | xargs -n1 basename | $$XARGS -I {{}} bash -eu -o pipefail -c "cd notebooks/ && AVATAR_BASE_URL=http://localhost:8000 AVATAR_USERNAME=user_integration AVATAR_PASSWORD=password_integration $(abspath $(VENV_NAME))/bin/python3.9 {{}} > /dev/null && echo \"Succesfully ran {{}}\""
.PHONY: test-tutorial


.DEFAULT_GOAL := help
help: Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} /^[\/\.a-zA-Z1-9_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
