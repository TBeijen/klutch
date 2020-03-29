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
```
{
    "python.pythonPath": "/Users/<user-name>/Library/Caches/pypoetry/virtualenvs/klutch-abcabc-py3.8"
}
