# Documentation

## Objective

The objective of this file is to describe how the build process of the documentation.

## Tools

We use `sphinx` to build our documentation, along with a few extensions.

- `sphinx.ext.autodoc`

  TODO: Explain to which files this applies to.

- `sphinx.ext.napoleon`

  TODO: Explain to which files this applies to.

- [`sphinx_multiversion`](https://holzhaus.github.io/sphinx-multiversion/master/quickstart.html)

  This is used to create multiple versions of the documentation.

- `sphinx.ext.autosummary`

  TODO: Explain to which files this applies to.

- `sphinxcontrib.autodoc_pydantic`

  This is used to generate documentation from `pydantic` models which come with useful information such as constrained values and a docstring per variable.

## Build process

Use `make doc-build` to build the documentation. Be on the lookout for errors during the build process, as `sphinx-multiversion` will not stop the build process on errors.

## Gotchas

`sphinx-multiversion` uses git to checkout the different branches and tags of the documentation. That means that any changes that you want to see being built MUST be committed. Any change that is not committed will not be taken into account.
