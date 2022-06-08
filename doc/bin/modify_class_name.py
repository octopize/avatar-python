import typer
import re
from pprint import pprint
from re import L
from bs4 import BeautifulSoup

from pathlib import Path


def main(path: Path):
    for file in path.glob("*.html"):
        with open(file, "r") as f:
            soup = BeautifulSoup(f, "html.parser")

        modified_soup = modify_class_name(soup)

        with open(file, "w") as f:
            f.write(str(modified_soup))


def modify_class_name(soup: BeautifulSoup) -> BeautifulSoup:
    """Example: replace avatars.api.Datasets by avatars.ApiClient.datasets"""

    all_classes = soup.find_all("span", {"class": "sig-prename descclassname"})
    client_class_definitions = [
        c.parent for c in all_classes if c.text == "avatars.api."
    ]

    module_names = [
        c.find_all("span", {"class": "pre"})[1] for c in client_class_definitions
    ]
    class_names = [
        c.find_all("span", {"class": "pre"})[2] for c in client_class_definitions
    ]

    for module_name, class_name in zip(module_names, class_names):
        module_name.string = "avatars.ApiClient."
        class_name.string = str(class_name.string).lower()

    return soup


if __name__ == "__main__":
    typer.run(main)
