# Avatar Python Client

## Documentation

Documentation is available here: https://python.docs.octopize.io/

## Requirements

The `avatars` package requires Python 3.9 or above.

## Tutorials

The tutorials are available in [`notebooks/`](./notebooks) as jupyter notebooks.

To be able to run those, you must install the `avatars` package and also the dependencies in `requirements-tutorial.txt`.

We provide a helper script to setup these inside a virtual environments and run the notebooks.

Simply run the following command:

(NOTE: This assumes that you have the `make` software installed. This may not be the case for Windows by default.)

```bash
make notebook
```

If you don't have access to `make` or you want to setup the tutorial requirements manually, you can follow the following commands:

These have to be run from the root of the `avatar-python` repo.

```shell
# Create and activate a new virtual environment.
python -m venv notebooks/env
source notebooks/env/bin/activate

# Install the necessary dependencies
pip install -r requirements-tutorial.txt
pip install . # installing avatars

#Exporting the necessary environment variables
export AVATAR_BASE_URL="https://yourcompany.octopize.app"
export AVATAR_USERNAME="your_username"
export AVATAR_PASSWORD="your_password"

# Launch the notebooks
jupyter notebook notebooks
```

## License

This software is made available through the Apache License 2.0

## Contact

help@octopize.io

## Releasing

See internal docs.
