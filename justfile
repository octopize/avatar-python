AVATAR_USERNAME := env_var_or_default("AVATAR_USERNAME", "user_integration")
AVATAR_PASSWORD := env_var_or_default("AVATAR_PASSWORD", "password_integration")
AVATAR_BASE_API_URL := env_var_or_default("AVATAR_BASE_API_URL", "http://localhost:8080/api")

DOC_SOURCE_DIR := "doc/source"
DOC_OUTPUT_DIR := env_var_or_default("DOC_OUTPUT_DIR", "doc/build/html")
OLD_CLIENT_OUTPUT_DIR := env_var_or_default("OLD_CLIENT_OUTPUT_DIR", "../../../avatar-python/")

USER_ID := env_var_or_default("USER_ID", `uuidgen`)
VENV_NAME := "notebooks/env"
TUTORIAL_REQUIREMENTS := "requirements-tutorial.txt"
TEST_TUTORIAL_FILE := "tests/integration/test_tutorials.py"
CURRENT_BRANCH:=`git branch --show-current`

import '../../justfiles/python.just'
import '../../justfiles/oci.just'
# Allow PY_PKG_NAME to be redefined because the name of the package is different from the name of the directory
set allow-duplicate-variables
PY_PKG_NAME := "avatars"

PY_EXTRA_DIR := "notebooks"

default:
    @just -l

notebook: generate-py pip-install-tutorial start-notebooks

set allow-duplicate-recipes
test-integration:
    just test-tutorials
test-tutorials: generate-py pip-install-tutorial run-test-tutorials
# Build the docs
doc-build:
    ##! This script is also used to deploy to production.
    ##! DO NOT modify this script without taking into account
    ##! the repercussions on the Github Actions script
    rm -rf {{DOC_OUTPUT_DIR}}
    mkdir -p {{DOC_OUTPUT_DIR}}
    just format-doc

    # Use standard sphinx-build instead of multiversion since we are getting "No matching refs found!"
    uv run sphinx-multiversion {{DOC_SOURCE_DIR}} {{DOC_OUTPUT_DIR}}

    # Now run the post-processing script on the generated HTML files
    uv run python doc/bin/modify_class_name.py {{DOC_OUTPUT_DIR}}

@format-doc:
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/tutorial.rst doc/source/tutorial.md
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/user_guide.rst doc/source/user_guide.md
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/changelog.rst CHANGELOG.md

@format-notebooks:
    uv run jupyter nbconvert --clear-output --ClearMetadataPreprocessor.enabled=True --inplace notebooks/*.ipynb
    @just lint-fix notebooks/


run-from-yaml PATH_TO_YAML:
    uv run ./bin/run_avatarization.py --yaml {{PATH_TO_YAML}}

# Build and open the documentation
doc: doc-build
    python3 -m webbrowser -t {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html

# Build and open the current documentation
doc-fast:
	uv run sphinx-build -b html {{DOC_SOURCE_DIR}} {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}
	echo {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html
	python3 -m webbrowser -t {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html


@generate-py:  ## Generate .py files from notebooks
    echo -n "Generating .py files from notebooks..."
    uv run jupytext notebooks/*.ipynb  --from ipynb --to py > /dev/null 2>&1
    just format-notebooks  > /dev/null 2>&1
    echo "Done"

[private]
@pip-requirements:
    echo -n "Generating requirements.txt from notebooks..."
    uv export  --only-group notebook -o {{TUTORIAL_REQUIREMENTS}} > /dev/null 2>&1
    echo "Done"

[private]
@pip-install-tutorial:
    just pip-requirements
    echo -n "Installing tutorial requirements..."
    python -m venv {{VENV_NAME}}
    "{{VENV_NAME}}/bin/python" -m pip install -r {{TUTORIAL_REQUIREMENTS}} > /dev/null 2>&1
    "{{VENV_NAME}}/bin/python" -m pip install . > /dev/null 2>&1
    "{{VENV_NAME}}/bin/python" -m pip install pytest pytest-xdist  > /dev/null 2>&1
    echo "Done"


[private]
start-notebooks:
    PATH="{{VENV_NAME}}/bin:$PATH" \
        VIRTUAL_ENV="{{VENV_NAME}}" \
        AVATAR_BASE_API_URL={{AVATAR_BASE_API_URL}} \
        AVATAR_USERNAME={{AVATAR_USERNAME}} \
        AVATAR_PASSWORD={{AVATAR_PASSWORD}} \
        jupyter notebook notebooks


[private]
run-test-tutorials:
    #! /usr/bin/env bash
    {{SHOPTS}}
    NB_FILES=$(find notebooks -name "*.ipynb" | wc -l)
    echo $NB_FILES
    if [ $NB_FILES -eq 0 ]; then
        echo "No notebooks found"
        exit 1
    fi

    PATH="{{VENV_NAME}}/bin:$PATH" \
    VIRTUAL_ENV="{{VENV_NAME}}" \
    AVATAR_BASE_API_URL={{AVATAR_BASE_API_URL}} \
    AVATAR_USERNAME={{AVATAR_USERNAME}} \
    AVATAR_PASSWORD={{AVATAR_PASSWORD}} \
    python -m pytest -n "$NB_FILES" {{TEST_TUTORIAL_FILE}}

[private]
copy-to-old-repo: ## Copy the files to the old python repo
    rsync -rav \
        --include="src/***" \
        --include="tests/***" \
        --include="CHANGELOG.md" \
        --include="uv.lock" \
        --include="pyproject.toml" \
        --include="justfile" \
        --include="requirements-tutorial.txt" \
        --include="notebooks/***" \
        --include="README.md" \
        --exclude="notebooks/env/***" \
        --exclude="**/__pycache__/***" \
        --exclude="*" . {{OLD_CLIENT_OUTPUT_DIR}}

[private]
publish: build
    #!/usr/bin/env bash
    {{SHOPTS}}
    # On CI, the token is stored in the environment variable UV_PUBLISH_TOKEN
    if [ -n "${UV_PUBLISH_TOKEN:-}" ]; then
        uv publish --token "$UV_PUBLISH_TOKEN"
    else
        uv publish --token "$(op items get 34o3isa4fvh2x64i5rbrq5dh6y --fields notesPlain)"
    fi
