from pathlib import Path

import typer
from bs4 import BeautifulSoup


def main(path: Path):
    for file in path.glob("*.html"):
        with open(file, "r") as f:
            soup = BeautifulSoup(f, "html.parser")

        modified_soup = modify_class_name(soup)

        with open(file, "w") as f:
            f.write(str(modified_soup))


def to_snake_case(s: str):
    return "".join(["_" + c.lower() if c.isupper() else c for c in str(s)]).strip("_")


def modify_class_name(soup: BeautifulSoup) -> BeautifulSoup:
    """Example: replace avatars.api.Datasets by avatars.ApiClient.datasets"""
    # Find all class entries in the docs
    all_classes = soup.find_all("dl", {"class": "py class"})
    if not all_classes:
        return soup

    # Extract the class/module signature from class entries starting with "avatars.api."
    client_and_api_class_definition_tags = [
        c.find("dt") for c in all_classes if "avatars.api." in c.find("dt").attrs["id"]
    ]

    # Get the module name tag from the signature
    module_name_tags = [
        c.find("span", {"class": "sig-prename descclassname"})
        for c in client_and_api_class_definition_tags
    ]
    module_name_tags = [c.find("span", {"class": "pre"}) for c in module_name_tags if c]

    # Get the class name tag from the signature
    class_name_tags = [
        c.find("span", {"class": "sig-name descname"})
        for c in client_and_api_class_definition_tags
    ]

    class_name_tags = [c.find("span", {"class": "pre"}) for c in class_name_tags if c]

    for module_name, class_name in zip(module_name_tags, class_name_tags):
        module_name.string = "avatars.ApiClient."
        class_name.string = to_snake_case(str(class_name.string))

    return soup


if __name__ == "__main__":
    typer.run(main)
