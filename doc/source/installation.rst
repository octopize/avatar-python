Installation
============

Prerequisites
-------------

``avatars`` is intended to be run with Python 3.9+.

Installation
------------

You can install the package from PyPI.

If you are migrating from the Github Releases to PyPI (prior to 0.7.3, May 7th 2024), make sure to uninstall the old package first.

.. code:: bash

   pip uninstall avatars

Then, install the package from PyPI.

Choose the latest version at https://pypi.org/project/octopize.avatar/

.. code:: bash

   # with pip
   pip install octopize.avatar

   # or, if you're using poetry (recommended)
   poetry add octopize.avatar


In your code, you can import the package like this:

.. code:: python

   from avatars.client import ApiClient
