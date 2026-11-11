from __future__ import annotations

from ..types import ObjCObject
from ..util import objc_class


def key_window() -> ObjCObject | None:
    """The app's key window (scene-based apps first, then the old ``keyWindow``)."""
    app = objc_class("UIApplication").sharedApplication
    for scene in app.connectedScenes.allObjects():
        for window in getattr(scene, "windows", None) or []:
            if window.isKeyWindow():  # a getter with a custom name: must be called
                return window
    fallback: ObjCObject | None = app.keyWindow
    return fallback


def root_view_controller() -> ObjCObject | None:
    """The key window's root view controller, to present sign-in sheets from."""
    window = key_window()
    return window.rootViewController if window is not None else None
