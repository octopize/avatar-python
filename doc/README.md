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

## Versioning

We want to show the documentation of all the different Python client versions. We thus use `sphinx-multiversion` to generate one version of the documentation for each release.

To show a sidebar to the user, we override the `ethical-ads.html` page that serves as a sidebar when deploying on ReadTheDocs. As we are only deploying on Github Pages, we can safely override this.

## Build process

Use `make doc-build` to build the documentation. Be on the lookout for errors during the build process, as `sphinx-multiversion` will not stop the build process on errors.

At version 0.6.0 and before, we were using `pydantic` version 1, which
combined with `sphinxcontrib.autodoc_pydantic` generates beautiful documentation
for pydantic.
Above 0.6.0, we switched to pydantic version 2. The problem arises that
`sphinx-multiversion` does not allow to run a pre-build callable that could install
the necessary dependencies depending on the current state of the repo,
and, although we can put custom code in `conf.py` that get's executed at
import, `sphinx-multiversion` only takes `conf.py` of the version you're building
_from_.
To circumvent that, we whitelist the tags that were at pydantic1 and have the following
workflow:

- Uninstall pydantic2 and install pydantic1
- Run `sphinx-multiversion` with the default values (the tag whitelist in `conf.py`)
- Uninstall pydantic1 and install pydantic2
- Run `sphinx-multiversion` with a configuration override via the CLI to build the documentation

## Gotchas

`sphinx-multiversion` uses git to checkout the different branches and tags of the documentation. That means that any changes that you want to see being built MUST be committed. Any change that is not committed will not be taken into account.
