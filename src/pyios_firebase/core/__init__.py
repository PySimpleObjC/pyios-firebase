"""Firebase Core: start Firebase once, when the app starts.

    from pyios_firebase import core

    core.configure()

Needs the ``FirebaseCore`` framework and ``GoogleService-Info.plist`` in the app.
"""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("configure", "default_app")


from ..util import objc_class


def configure() -> None:
    """Start Firebase with the app's ``GoogleService-Info.plist``.

    Call it once, at app start, before using any other product. To use the
    App Check debug provider, call ``app_check.initialize_debug_appcheck()``
    first.
    """
    objc_class("FIRApp").configure()


def default_app() -> ObjCObject | None:
    """The default ``FIRApp``, or ``None`` if ``configure()`` was not called."""
    return objc_class("FIRApp").defaultApp()
