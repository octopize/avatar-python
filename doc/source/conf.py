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
import sys
from typing import Optional

sys.path.insert(
    0, os.path.abspath("../../avatars/")
)  # Source code dir relative to this file

# -- Project information -----------------------------------------------------

project = "avatars"
copyright = "2022, Octopize"
author = "Octopize"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

autodoc_default_options = {
    "exclude-members": "get_health_db, get_health_task, default_encoder, login",
    "undoc-members": True,  # weird, have to add this so that the avatars.client module is documented
}
autodoc_typehints_format = "short"
# autodoc_typehints_format is not applied to attributes:
# See https://github.com/sphinx-doc/sphinx/issues/10290
python_use_unqualified_type_names = True


templates_path = ["_templates"]

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
    'avatars.api.Health(client: ApiClient)' into 'avatars,ApiClient.health' to
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
