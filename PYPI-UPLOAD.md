
Because the new, big current software crisis is in the hopelesly complicated area of software packaging is so huge, I can only cope an hope that what is mentioned below still works the next time I want to upload this software to PyPi.

I'll spare you the rant, but to summarize, it is about the pollution with configuration files in projects, workspaces, laptops, home directories, environment and what not, only to get something working in a brittle silo for as long as one might optimistically hope for.

So:
    - we need a pyproject.xml to polute our project we shared on github, because it is required by `build`
    - we need a MANIFEST.in, idem, because it is needed by setuptools
    - we need a ~/.pypirc with keys generated on PyPi.org because `twine` needs that.

Then
In de root directory do (yes you need all of those packages): 
    - pip install build
    - pip install setuptools
    - pip install twine
    - rm -rf dist/
    - python -m build
    - python -m twine upload dist/*

You might test it locally by, -e allowing for local edits being possible:
    - pip install -e .
    - pip uninstall asp-selftest

It looks for a pyproject.toml and does it's thing.

It seems to me that to publish a package, we'd better create a separate project.
Anyway, this is here to remember.
