# Release Procedure

```shell
# Remove old build artifacts
rm -r build dist lib/cfv.egg-info
find lib/ test/ -name *.pyc -delete
find lib/ test/ -name __pycache__ -delete
git status --ignored

# Bump version
vim lib/cfv/common.py
vim Changelog
git add lib/cfv/common.py Changelog
git diff --cached
git commit -m "Update Changelog and bump version to <version>"
git push

# Tag version
git tag v<version>
git push --tags

# Build & Upload
docker run --pull=always --rm -it -v $(pwd):/app -w /app -u $(id -u):$(id -g) -e HOME=/tmp python:latest sh -c "pip install build && python -m build && pip install twine && ~/.local/bin/twine check dist/* && ~/.local/bin/twine upload dist/*"

# Bump version
vim lib/cfv/common.py
vim Changelog
git add lib/cfv/common.py Changelog
git diff --cached
git commit -m "Bump version"
git push
```
