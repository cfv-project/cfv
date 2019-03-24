# Release Procedure

```shell
rm -rf __pycache__ build dist lib/cfv.egg-info
git status
git tag <version>
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
