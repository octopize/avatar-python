AVATAR_USERNAME := env_var_or_default("AVATAR_USERNAME", "user_integration")
AVATAR_PASSWORD := env_var_or_default("AVATAR_PASSWORD", "password_integration")
AVATAR_BASE_API_URL := env_var_or_default("AVATAR_BASE_API_URL", "http://localhost:8080/api")

DOC_SOURCE_DIR := "doc/source"
DOC_OUTPUT_DIR := env_var_or_default("DOC_OUTPUT_DIR", "doc/build/html")

import? 'local-dev.just'

USER_ID := env_var_or_default("USER_ID", `uuidgen`)
VENV_NAME := "notebooks/env"
TUTORIAL_REQUIREMENTS := "requirements-tutorial.txt"
CURRENT_BRANCH:=`git branch --show-current`

default:
    @just -l

upload FILE :
    uv run bin/upload.py upload {{FILE}} {{USER_ID}} `basename {{FILE}}`

download KEY OUTPUT_FILE :
    uv run bin/upload.py download {{KEY}} {{USER_ID}} {{OUTPUT_FILE}}

upload-download INPUT_FILE:
    USER_ID=deadbeef-1234-5678-9abc-def012345678 just upload {{INPUT_FILE}}
    USER_ID=deadbeef-1234-5678-9abc-def012345678 just download `basename {{INPUT_FILE}}` `basename {{INPUT_FILE}}`.downloaded

pip-requirements:
	uv export  --only-group notebook -o {{TUTORIAL_REQUIREMENTS}}

pip-install-tutorial:
    just pip-requirements
    python -m venv {{VENV_NAME}}
    "{{VENV_NAME}}/bin/python3" -m pip install -r {{TUTORIAL_REQUIREMENTS}}
    "{{VENV_NAME}}/bin/python3" -m pip install .
    "{{VENV_NAME}}/bin/python3" -m pip install pytest pytest-xdist

notebook:
    just pip-install-tutorial
    PATH="{{VENV_NAME}}/bin:$PATH" VIRTUAL_ENV="{{VENV_NAME}}" AVATAR_BASE_API_URL={{AVATAR_BASE_API_URL}} AVATAR_USERNAME={{AVATAR_USERNAME}} AVATAR_PASSWORD={{AVATAR_PASSWORD}} jupyter notebook notebooks

# Build the docs
doc-build:
    ##! This script is also used to deploy to production.
    ##! DO NOT modify this script without taking into account
    ##! the repercussions on the Github Actions script
    rm -rf {{DOC_OUTPUT_DIR}}
    mkdir -p {{DOC_OUTPUT_DIR}}
    just format-doc

    # Use standard sphinx-build instead of multiversion since we're getting "No matching refs found!"
    uv run sphinx-multiversion {{DOC_SOURCE_DIR}} {{DOC_OUTPUT_DIR}}

    # Now run the post-processing script on the generated HTML files
    uv run python doc/bin/modify_class_name.py {{DOC_OUTPUT_DIR}}

format-doc:
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/tutorial.rst doc/source/tutorial.md
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/user_guide.rst doc/source/user_guide.md
	uv run pandoc --from=markdown --to=rst --output={{DOC_SOURCE_DIR}}/changelog.rst CHANGELOG.md


# Build and open the documentation
doc: doc-build
    python3 -m webbrowser -t {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html

# Build and open the current documentation
doc-fast:
	uv run sphinx-build -b html {{DOC_SOURCE_DIR}} {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}
	echo {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html
	python3 -m webbrowser -t {{DOC_OUTPUT_DIR}}/{{CURRENT_BRANCH}}/index.html
