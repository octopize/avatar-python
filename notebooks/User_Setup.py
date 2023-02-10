# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.2
# ---

# # User account activation and set password

# ## Configuration
#
# You can put your own configuration here

# +
# If not defined in your environment variables you can overload your avatar API url here :
avatar_url = ""

# Start by only providing the email, you will then get a token by email.
email = ""

# Once you get that token by mail, you can fill it below along with a new password.
token = ""
new_password = ""
# -

# ## Script itself

# +
from avatars.client import ApiClient
import os

if avatar_url is None or avatar_url == "":
    avatar_url = os.environ.get("AVATAR_BASE_URL")

client = ApiClient(base_url=avatar_url)

if token == "" or token is None:
    client.forgotten_password(email)
else:
    if new_password == "" or new_password is None:
        raise ValueError("Password is mandatory")

    client.reset_password(
        email=email,
        new_password=new_password,
        new_password_repeated=new_password,
        token=token,
    )
