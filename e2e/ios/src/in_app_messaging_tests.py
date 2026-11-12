"""In-App Messaging end-to-end tests (no emulator exists: the SDK runs for real,
and fetches nothing for the demo project).

Firebase's default screens are checked with a message made here: the SDK's
default display shows it over the Kivy window, the impression comes after 3
seconds on screen, and the test taps the real button (its UIKit action).
"""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from runner import TestContext, expect, expect_equal

from pyios_firebase.in_app_messaging import (
    Action,
    DisplayDelegate,
    InAppMessage,
    InAppMessaging,
    MessageType,
    ModalMessage,
    TriggerType,
)
from pyios_firebase.util import objc_class

URL = "https://example.com/e2e-in-app"
TOUCH_UP_INSIDE = 1 << 6  # UIControlEventTouchUpInside


def _color(r: float, g: float, b: float) -> Any:
    return objc_class("UIColor").colorWithRed_green_blue_alpha_(r, g, b, 1.0)


def native_modal(campaign: str) -> Any:
    """A FIRInAppMessagingModalDisplay, as Firebase makes from a campaign
    (its initializer is public for tests)."""
    button = objc_class("FIRInAppMessagingActionButton").alloc()
    button = button.initWithButtonText_buttonTextColor_backgroundColor_(
        "Shop now", _color(1, 1, 1), _color(0, 0.5, 1)
    )
    modal = objc_class("FIRInAppMessagingModalDisplay").alloc()
    return modal.initWithCampaignName_titleText_bodyText_textColor_backgroundColor_imageData_actionButton_actionURL_appData_(
        campaign,
        "50% off",
        "today only",
        _color(0, 0, 0),
        _color(1, 1, 1),
        None,
        button,
        objc_class("NSURL").URLWithString_(URL),
        {"screen": "shop"},
    )


def _class_name(value: Any) -> str:
    return str(value.objc_class.name) if value is not None else "nil"


def test_in_app_messaging_settings(t: TestContext) -> None:
    iam = InAppMessaging.in_app_messaging()
    expect_equal(
        _class_name(iam.native.messageDisplayComponent),
        "FIRIAMDefaultDisplayImpl",
        "Firebase's display is set at configure",
    )
    expect_equal(iam.message_display_suppressed, False, "not suppressed at launch")
    iam.message_display_suppressed = True
    expect_equal(iam.message_display_suppressed, True, "suppressed")
    iam.message_display_suppressed = False
    collecting = iam.automatic_data_collection_enabled
    expect(isinstance(collecting, bool), "data collection flag")
    iam.automatic_data_collection_enabled = not collecting
    expect_equal(iam.automatic_data_collection_enabled, not collecting, "flag set")
    iam.automatic_data_collection_enabled = collecting
    iam.trigger_event("e2e_level_done")  # no campaign: nothing shows
    for bad, error in [("", ValueError), (None, TypeError)]:
        try:
            iam.trigger_event(bad)  # type: ignore[arg-type]
        except error:
            continue
        raise AssertionError(f"trigger_event({bad!r}): no {error.__name__}")
    t.passed()


def test_in_app_messaging_python_display(t: TestContext) -> None:
    """A Python display, called by Objective-C as Firebase calls it, reports
    back through the real FIRInAppMessagingAction class to the listeners."""
    iam = InAppMessaging.in_app_messaging()
    got: list[Any] = []
    removers = [
        iam.add_impression_listener(lambda m: got.append(("impression", m.campaign.campaign_name))),
        iam.add_click_listener(lambda m, a: got.append(("click", a))),
    ]

    def show(message: InAppMessage, delegate: DisplayDelegate) -> None:
        got.append(("shown", message))
        delegate.impression()
        delegate.clicked()

    iam.set_display(show)
    try:
        component = iam.native.messageDisplayComponent
        expect_equal(_class_name(component), "PyInAppMessagingDisplay", "the Python display")
        component.displayMessage_displayDelegate_(
            native_modal("e2e python display"), InAppMessaging._delegate
        )
        shown = got[0][1]
        expect(isinstance(shown, ModalMessage), f"a ModalMessage: {shown!r}")
        expect_equal(shown.type, MessageType.MODAL, "type")
        # the SDK's public initializers set "on an Analytics event"
        expect_equal(shown.trigger_type, TriggerType.ON_ANALYTICS_EVENT, "trigger")
        expect_equal(shown.title, "50% off", "title")
        expect_equal(shown.body, "today only", "body")
        expect_equal(shown.text_color, "#000000", "text color")
        expect_equal(shown.action_button.text, "Shop now", "button")
        expect_equal(shown.action_button.background_color, "#0080FF", "button color")
        expect_equal(shown.action_url, URL, "action URL")
        expect_equal(shown.app_data, {"screen": "shop"}, "app data")
        expect_equal(
            got[1:],
            [("impression", "e2e python display"), ("click", Action("Shop now", URL))],
            "the listeners",
        )
    finally:
        iam.use_default_display()
        for remove in removers:
            remove()
    expect_equal(
        _class_name(iam.native.messageDisplayComponent),
        "FIRIAMDefaultDisplayImpl",
        "Firebase's display again",
    )
    t.passed()


def _find_button(view: Any, title: str) -> Any:
    if view.isKindOfClass(objc_class("UIButton")) and str(view.titleForState_(0) or "") == title:
        return view
    subviews = view.subviews
    if callable(subviews):  # Rubicon may give the property as a method
        subviews = subviews()
    for sub in subviews:
        found = _find_button(sub, title)
        if found is not None:
            return found
    return None


def _windows() -> list[Any]:
    """Every window of the app's scenes."""
    found = []
    for scene in objc_class("UIApplication").sharedApplication.connectedScenes.allObjects():
        try:
            found.extend(scene.windows)
        except AttributeError:  # not a UIWindowScene
            continue
    return found


def _message_window() -> Any:
    """The visible window Firebase's display shows its messages in."""
    for window in _windows():
        root = window.rootViewController
        if root is not None and not window.isHidden() and _class_name(root).startswith("FIRIAM"):
            return window
    return None


def _describe_windows() -> str:
    return "; ".join(
        f"{_class_name(w)} hidden={bool(w.isHidden())} root={_class_name(w.rootViewController)}"
        for w in _windows()
    )


def test_in_app_messaging_default_display(t: TestContext) -> None:
    """Firebase's own modal over the Kivy window: impression, then a tap on
    its button reaches the click listener."""
    iam = InAppMessaging.in_app_messaging()
    state: dict[str, Any] = {"impression": None, "click": None, "polls": 0}
    removers = [
        iam.add_impression_listener(lambda m: state.update(impression=m)),
        iam.add_click_listener(lambda m, a: state.update(click=(m, a))),
    ]

    def finish(error: str | None = None) -> None:
        for remove in removers:
            remove()
        if error is None:
            t.passed()
        else:
            t.fail(error)

    def wait_for_click(_dt: float) -> None:
        if state["click"] is None:
            Clock.schedule_once(t.step(wait_for_click), 0.2)
            return
        message, action = state["click"]
        expect_equal(message.campaign.campaign_name, "e2e default display", "clicked message")
        expect_equal(action, Action("Shop now", URL), "the tapped action")
        expect(_message_window() is None, "the message closed")
        finish()

    def wait_for_impression(_dt: float) -> None:
        state["polls"] += 1
        if state["impression"] is None:
            if state["polls"] > 60:
                finish("no impression within 12 s")
                return
            Clock.schedule_once(t.step(wait_for_impression), 0.2)
            return
        expect_equal(state["impression"].title, "50% off", "impression message")
        window = _message_window()
        expect(window is not None, f"Firebase's message window, in: {_describe_windows()}")
        button = _find_button(window, "Shop now")
        expect(button is not None, "the action button")
        button.sendActionsForControlEvents_(TOUCH_UP_INSIDE)
        Clock.schedule_once(t.step(wait_for_click), 0.2)

    display = objc_class("FIRIAMDefaultDisplayImpl").alloc().init()
    iam.add_dismiss_listener(lambda m, d: None)()  # makes sure the delegate exists
    display.displayMessage_displayDelegate_(
        native_modal("e2e default display"), InAppMessaging._delegate
    )
    state["display"] = display  # kept while it shows
    Clock.schedule_once(t.step(wait_for_impression), 0.5)


TESTS = [(name, fn) for name, fn in globals().items() if name.startswith("test_in_app_messaging")]
