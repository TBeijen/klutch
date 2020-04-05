Klutch
======

> Putting your HPAs into overdrive






TODO
----
- Finding own/current namespace
- How is listing objects affected by having limited RBAC permissions?
- Parallelism (webserver for triggers, control loop, metrics server)
- e2e testing (kind?)
- Triggers via AWS SNS
- Notifications (Slack)
- Golang?

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
    "python.pythonPath": "/Users/<user-name>/Library/Caches/pypoetry/virtualenvs/klutch-abcabc-py3.8"
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
