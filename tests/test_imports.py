import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "pyios_firebase",
        "pyios_firebase.core",
        "pyios_firebase.firestore",
        "pyios_firebase.types",
        "pyios_firebase.util",
    ],
)
def test_imports_without_firebase_frameworks(module):
    """Importing must not need any Firebase class: they are looked up on use."""
    importlib.import_module(module)
