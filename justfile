AVATAR_USERNAME := env_var("AVATAR_USERNAME")
AVATAR_PASSWORD := env_var("AVATAR_PASSWORD")
AVATAR_BASE_API_URL := env_var_or_default("AVATAR_BASE_API_URL", "http://localhost:8080/api")

USER_ID := env_var_or_default("USER_ID", `uuidgen`)
VENV_NAME := "notebooks/env"
TUTORIAL_REQUIREMENTS := "requirements-tutorial.txt"
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