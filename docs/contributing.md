# Contributing to Saiph

## Releasing a new version

This whole procedure has to be done on the `main` branch, as the Github workflow will
automatically create a release when a tag is created, wherever it is.
And unfortunately, we can't combine tags and branch conditions on push
events. More info [here](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#push) and [here](https://stackoverflow.com/questions/57963374/github-actions-tag-filter-with-branch-filter).

```bash
VERSION="0.2.0"

# 1. Edit version in `pyproject.toml` and `avatars/__init__.py`

# 2. Add to next commit
git add pyproject.toml avatars/__init__.py

# 3. Commit
git commit -am "chore: release version $VERSION"

# 4. Tag
git tag $VERSION

# 4. Push
git push && git push --tags
```
