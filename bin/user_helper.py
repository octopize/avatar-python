#!/usr/bin/env python3
from avatars.client import ApiClient
import os
import typer

# To run this script, 
# You need to be in avatar-python repository
# Then poetry run ./bin/user_helper.py

app = typer.Typer(help="""
This script allow to generate a token and then change your password.
You are expected to call generate_token first, then change_password.
""")

def load_client(base_url: str) -> ApiClient:
    if base_url is None or base_url == "":
        print("ERROR: Base url should be provided, you can do it through the env variable AVATAR_BASE_URL.")
        return None
    return ApiClient(base_url=base_url)

@app.command()
def generate_token(email: str, base_url:str=os.environ.get("AVATAR_BASE_URL"), ):
    """
    Generate a validation token which is done by providing the application url and only an email
    """
    client = load_client(base_url)
    print(f"Resetting password for {email}, check your email for your token")
    client.forgotten_password(email)

@app.command()
def change_password(email: str, token: str, new_password: str, new_password_confirm: str, base_url:str=os.environ.get("AVATAR_BASE_URL"), ):
    """
    Resetting the account with a password, which is done by providing all parameters.
    """
    client = load_client(base_url)
    print(f"Validating new password for {email}")
    client.reset_password(
    email=email, 
    new_password=new_password, 
    new_password_repeated=new_password_confirm, 
    token=token)

if __name__ == "__main__":
    app()