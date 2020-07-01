Klutch
======

![](https://github.com/tbeijen/klutch/workflows/CI%2FCD/badge.svg)

> Putting your HPAs into overdrive

Resources
---------

Kubernetes Python SDK
* https://github.com/kubernetes-client/python/tree/master/kubernetes#documentation-for-api-endpoints
* https://github.com/kubernetes-client/python/tree/master/examples

JSON patch
* https://tools.ietf.org/html/rfc6902
* http://jsonpatch.com/#json-pointer


Running sample
--------------

Pick or create a namespace.

```sh
examples/redeploy.sh --namespace=<demo-namespace>

python -m klutch --namespace=<demo-namespace>
```


Development setup
-----------------

```
# When on OSX, might be needed to install python version first, e.g. using pyenv
pyenv install 3.8.2
poetry env use -vvvv ~/.pyenv/versions/3.8.2/bin/python3.8

poetry install
poetry shell
pre-commit install

python -m klutch --dry-run
```

### Debugging in VScode

`.vscode/launch.json`:
```
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Module",
            "type": "python",
            "request": "launch",
            "module": "klutch",
            "args" : ["--dry-run"]
        }
    ]
}
```

`.vscode/settings.json` (note the path when starting `poetry shell`):

```json
{
    "python.pythonPath": "/Users/<user-name>/Library/Caches/pypoetry/virtualenvs/klutch-abcabc-py3.8"
}
```

### Running and debugging tests in VScode

Via `cmd` + `shift` + `p`: 'Python: Discover Tests`.

Test option (lab flask icon) should appear in left bar.

`.vscode/settings.json` now includes:

```json
{
    "python.pythonPath": "/Users/<user-name>/Library/Caches/pypoetry/virtualenvs/klutch-abcabc-py3.8",
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.testing.unittestEnabled": false,
    "python.testing.nosetestsEnabled": false,
    "python.testing.pytestEnabled": true
}
```

Be sure to open the output panel 'Python Test Log'.

#### Enabling debugging of library code:

Reference:

* https://code.visualstudio.com/docs/python/testing#_debug-tests
* (via: https://github.com/microsoft/ptvsd/issues/2073#issuecomment-589469906)

Add to `.vscode/launch.json` (under `configurations`):

```json
        {
            "name": "Python: Unit Tests",
            "type": "python",
            "request": "test",
            "justMyCode": false,
        }
```

Github workflow
---------------

Workflow using Github actions

- Job test: Runs on all commits
- Job publish: Runs on tags only
