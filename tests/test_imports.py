import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "pyios_firebase",
        "pyios_firebase.analytics",
        "pyios_firebase.app_check",
        "pyios_firebase.auth",
        "pyios_firebase.auth.apple",
        "pyios_firebase.auth.facebook",
        "pyios_firebase.auth.google",
        "pyios_firebase.auth.multi_factor",
        "pyios_firebase.core",
        "pyios_firebase.crashlytics",
        "pyios_firebase.database",
        "pyios_firebase.firestore",
        "pyios_firebase.functions",
        "pyios_firebase.in_app_messaging",
        "pyios_firebase.messaging",
        "pyios_firebase.messaging.notifications",
        "pyios_firebase.performance",
        "pyios_firebase.remote_config",
        "pyios_firebase.storage",
        "pyios_firebase.types",
        "pyios_firebase.util",
    ],
)
def test_imports_without_firebase_frameworks(module):
    """Importing must not need any Firebase class: they are looked up on use."""
    importlib.import_module(module)
