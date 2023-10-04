# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import subprocess
import sys
from datetime import date
from subprocess import PIPE
from typing import Optional

sys.path.insert(
    0, os.path.abspath("../../avatars/")
)  # Source code dir relative to this file

from avatars import __version__  # noqa: E402

# -- Project information -----------------------------------------------------

project = "avatars"
copyright = f"{date.today().year}, Octopize"
author = "Octopize"
version = __version__
release = __version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_multiversion",
    "sphinx.ext.autosummary",
    "sphinxcontrib.autodoc_pydantic",
]

autodoc_default_options = {
    "exclude-members": "login, get_job, to_common_type",
    # weird, have to add this so that the avatars.client module is documented
    "undoc-members": True,
}
autodoc_typehints_format = "short"
autodoc_member_order = "bysource"

# autodoc_typehints_format is not applied to attributes:
# See https://github.com/sphinx-doc/sphinx/issues/10290
python_use_unqualified_type_names = True

# -- Sphinx Multi-version -------------------------------------------------
# https://autodoc-pydantic.readthedocs.io/en/stable/users/configuration.html
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config = False
autodoc_pydantic_model_signature_prefix = "class"
autodoc_pydantic_field_doc_policy = "description"
autodoc_pydantic_field_signature_prefix = " "
autodoc_pydantic_model_show_field_summary = False

# -------------------------------------------------------------------------

templates_path = ["_templates"]

# -- Sphinx Multi-version -------------------------------------------------
# https://holzhaus.github.io/sphinx-multiversion/master/configuration.html

# create a version for main and current branch to be able to see layout during development
proc = subprocess.Popen(
    args=("git", "branch", "--show-current"), stdout=PIPE, text=True
)
current_branch, _ = proc.communicate()
smv_branch_whitelist = f"^(main|{current_branch.strip()})$"
# Tags define a release, which are the ones that show up on the sidebar.
# Add the pattern for which you want the releases to appear.
smv_released_pattern = r"^(refs/tags/.*|main$)"

# See [doc/README.md](doc/README.md) for explanation on the regex.
smv_tag_whitelist = r"^(0\.[0-5].[0-9]+|0.6.0)$"

# -------------------------------------------------------------------------

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"
html_static_path = ["_static"]


def modify_class_signature(app, what, name, obj, options, signature, return_annotation):
    """Remove attribute 'client: ApiClient' from modified classnames.

    Using bin/modify_class_names.py, and this method here, we modify
    'avatars.api.Health(client: ApiClient)' into 'avatars.ApiClient.health' to
    be in line with the designed use of the API.
    """

    if signature and "client: ApiClient" in signature:
        signature = "()"

    return (signature, return_annotation)


def autodoc_skip_member(app, what, name, obj, skip, options) -> Optional[bool]:
    # Skip avatars.api.Auth
    if what == "module" and name == "Auth":
        return True
    return None


def setup(app):
    app.connect("autodoc-process-signature", modify_class_signature)
    app.connect("autodoc-skip-member", autodoc_skip_member)
