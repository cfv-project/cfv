# Release Procedure

```shell
rm -rf __pycache__ build dist lib/cfv.egg-info
git status
vim lib/cfv/common.py
vim Changelog
git add lib/cfv/common.py Changelog
git diff --cached
git commit -m "Update Changelog and bump version to <version>"
git push
git tag v<version>
git push --tags
python setup.py sdist bdist_wheel
twine check dist/*
twine upload dist/*
vim lib/cfv/common.py
vim Changelog
git add lib/cfv/common.py Changelog
git diff --cached
git commit -m "Bump version"
git push
```
