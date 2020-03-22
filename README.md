Klutch
======

> Putting horizontal pod autoscalers into overdrive






Development setup
-----------------

```
# When on OSX, might be needed to install python version first, e.g. using pyenv
pyenv install 3.8.2
poetry env use -vvvv ~/.pyenv/versions/3.8.2/bin/python3.8

poetry install
poetry shell

python -m klutch --dry-run
```
