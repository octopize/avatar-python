Client
======

The ApiClient object
--------------------

The Python client acts as an interface that communicates with the avatarization engine.
For more information about the concepts and avatarization, checkout our main docs.

The :class:`ApiClient <avatars.client.ApiClient>` is the main interfaces that you should use.
You'll instantiate it, and authenticate using the credentials to the engine.

.. note::
   The :meth:`request() <avatars.client.ApiClient.request>` method is
   only there if you want to make a manual call to the engine.
   For regular use, use the methods described below.


.. automodule:: avatars.client
   :members:


Methods
-------

Here below are the methods provided that communicate with the engine.
The API they expose uses `pydantic <https://pydantic-docs.helpmanual.io/>`_
objects to help you pass in the correct arguments to the methods.


.. automodule:: avatars.api
   :members:
   :undoc-members:
