# Avatar Python Client

## Requirements

The `avatars` package requires Python 3.12 or above.

## Tutorials

The tutorials are available in [`notebooks/`](./notebooks) as jupyter notebooks.

To be able to run those, you must install the `avatars` package and also the notebook dependencies exported to a local `requirements-tutorial.txt` file. That file is generated locally and is not committed to the repository.

We provide a helper script to setup these inside a virtual environments and run the notebooks.

Simply run the following command:

(NOTE: This assumes that you have the `just` software installed. This may not be the case for Windows by default.)

```bash
just notebook
```

If you don't have access to `just` or you want to setup the tutorial requirements manually, first export the tutorial requirements file:

```bash
uv export --only-group notebook -o requirements-tutorial.txt
```

Then follow the installation section.

## Installation

### with pip

```bash
pip install octopize.avatar
```

### or, if you're using uv

```bash
uv add octopize.avatar
```

### or, if you're using poetry

```bash
poetry add octopize.avatar
```

## License

This software is made available through the Apache License 2.0.

## Contact

<help@octopize.io>

## Releasing

See internal docs.
