"""Every module must import: a syntax error in one the other tests don't touch
(like the composition root) would otherwise only show up in the built .exe."""

import importlib
import pkgutil

import airpods_sync


def test_every_module_imports():
    names = [
        module.name
        for module in pkgutil.walk_packages(airpods_sync.__path__, "airpods_sync.")
        if not module.name.endswith("__main__")  # importing it runs the app
    ]

    for name in names:
        importlib.import_module(name)

    assert "airpods_sync.cli.main" in names
