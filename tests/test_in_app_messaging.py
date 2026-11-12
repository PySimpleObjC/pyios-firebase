from ctypes import c_bool, c_long

import pytest
from conftest import Recorder
from rubicon.objc import NSObject, ObjCClass, objc_id, objc_method, objc_property
from rubicon.objc.runtime import load_library

from pyios_firebase.in_app_messaging import (
    IN_APP_MESSAGING_ERROR_DOMAIN,
    Action,
    ActionButton,
    BannerMessage,
    CardMessage,
    DismissType,
    ImageOnlyMessage,
    InAppMessage,
    InAppMessaging,
    InAppMessagingErrorCode,
    MessageType,
    ModalMessage,
    TriggerType,
    default_action,
)
from pyios_firebase.in_app_messaging import in_app_messaging as module
from pyios_firebase.in_app_messaging.in_app_messaging import (
    PyInAppMessagingDelegate,
    PyInAppMessagingDisplay,
)
from pyios_firebase.in_app_messaging.messages import color_to_hex, message_from_native
from pyios_firebase.util import objc_instance

load_library("AppKit")
NSColor = ObjCClass("NSColor")


def rgb(r, g, b, a=1.0):
    # NSColor answers getRed:green:blue:alpha: as UIColor does
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, a)


class FakeCampaign(NSObject):
    messageID = objc_property()
    campaignName = objc_property()
    renderAsTestMessage = objc_property(c_bool)


class FakeImage(NSObject):
    imageURL = objc_property()
    imageRawData = objc_property()


class FakeButton(NSObject):
    buttonText = objc_property()
    buttonTextColor = objc_property()
    buttonBackgroundColor = objc_property()


class FakeAction(NSObject):
    actionText = objc_property()
    actionURL = objc_property()


class FakeMessage(NSObject):
    """Has the properties of every message class."""

    campaignInfo = objc_property()
    type = objc_property(c_long)
    triggerType = objc_property(c_long)
    appData = objc_property()
    title = objc_property()
    bodyText = objc_property()
    body = objc_property()
    textColor = objc_property()
    displayBackgroundColor = objc_property()
    imageData = objc_property()
    actionButton = objc_property()
    actionURL = objc_property()
    portraitImageData = objc_property()
    landscapeImageData = objc_property()
    primaryActionButton = objc_property()
    primaryActionURL = objc_property()
    secondaryActionButton = objc_property()
    secondaryActionURL = objc_property()


def url(text):
    return ObjCClass("NSURL").URLWithString_(text)


def fake_message(kind=MessageType.MODAL):
    campaign = FakeCampaign.alloc().init()
    campaign.messageID = "m-1"
    campaign.campaignName = "Spring sale"
    campaign.renderAsTestMessage = True
    image = FakeImage.alloc().init()
    image.imageURL = "https://example.com/a.png"
    image.imageRawData = ObjCClass("NSData").dataWithBytes_length_(b"\x89PNG", 4)
    button = FakeButton.alloc().init()
    button.buttonText = "Shop"
    button.buttonTextColor = rgb(1, 1, 1)
    button.buttonBackgroundColor = rgb(0, 0.5, 1, 0.5)
    message = FakeMessage.alloc().init()
    message.campaignInfo = campaign
    message.type = kind
    message.triggerType = TriggerType.ON_ANALYTICS_EVENT
    message.appData = {"screen": "shop"}
    message.title = "50% off"
    message.bodyText = "today only"
    message.body = "card body"
    message.textColor = rgb(0, 0, 0)
    message.displayBackgroundColor = rgb(1, 0, 0)
    message.imageData = image
    message.actionButton = button
    message.actionURL = url("myapp://shop")
    message.portraitImageData = image
    message.primaryActionButton = button
    message.primaryActionURL = url("myapp://card")
    return message


def test_color_to_hex():
    assert color_to_hex(rgb(1, 0.5, 0)) == "#FF8000"
    assert color_to_hex(rgb(0, 0, 0, 0.5)) == "#00000080"
    assert color_to_hex(None) is None


def test_modal_from_native():
    message = message_from_native(fake_message())
    assert isinstance(message, ModalMessage)
    assert message.campaign.message_id == "m-1"
    assert message.campaign.campaign_name == "Spring sale"
    assert message.campaign.render_as_test_message is True
    assert message.trigger_type == TriggerType.ON_ANALYTICS_EVENT
    assert message.app_data == {"screen": "shop"}
    assert (message.title, message.body) == ("50% off", "today only")
    assert (message.text_color, message.background_color) == ("#000000", "#FF0000")
    assert message.image.image_url == "https://example.com/a.png"
    assert message.image.image_data == b"\x89PNG"
    assert message.action_button == ActionButton("Shop", "#FFFFFF", "#0080FF80")
    assert message.action_url == "myapp://shop"


def test_other_types_from_native():
    banner = message_from_native(fake_message(MessageType.BANNER))
    assert isinstance(banner, BannerMessage) and banner.body == "today only"
    card = message_from_native(fake_message(MessageType.CARD))
    assert isinstance(card, CardMessage)
    assert card.body == "card body" and card.primary_button.text == "Shop"
    assert card.primary_action_url == "myapp://card"
    assert card.secondary_button is None and card.landscape_image is None
    image = message_from_native(fake_message(MessageType.IMAGE_ONLY))
    assert isinstance(image, ImageOnlyMessage) and image.action_url == "myapp://shop"
    unknown = message_from_native(fake_message(9))
    assert type(unknown) is InAppMessage and unknown.type == 9


def test_default_action():
    assert default_action(message_from_native(fake_message())) == Action(
        "Shop", "myapp://shop"
    )
    card = message_from_native(fake_message(MessageType.CARD))
    assert default_action(card) == Action("Shop", "myapp://card")
    banner = message_from_native(fake_message(MessageType.BANNER))
    assert default_action(banner) == Action(None, "myapp://shop")


# ---- InAppMessaging ---------------------------------------------------------------


@pytest.fixture
def iam():
    native = Recorder()
    native.messageDisplaySuppressed = False
    native.automaticDataCollectionEnabled = True
    yield InAppMessaging(native), native
    for listeners in InAppMessaging._listeners.values():
        listeners.clear()
    InAppMessaging._delegate = None
    InAppMessaging._display = None
    InAppMessaging._display_handler = None


def test_settings_and_events(iam):
    iam, native = iam
    assert iam.message_display_suppressed is False
    iam.message_display_suppressed = True
    assert native.messageDisplaySuppressed is True
    assert iam.automatic_data_collection_enabled is True
    iam.automatic_data_collection_enabled = False
    assert native.automaticDataCollectionEnabled is False
    iam.trigger_event("level_done")
    assert native.last("triggerEvent_") == ("level_done",)
    with pytest.raises(ValueError):
        iam.trigger_event("")
    with pytest.raises(TypeError):
        iam.trigger_event(None)


def test_listeners_get_what_the_delegate_gets(iam):
    iam, native = iam
    got = []
    remove = iam.add_impression_listener(lambda m: got.append(("seen", m.title)))
    iam.add_click_listener(lambda m, a: got.append(("click", a)))
    iam.add_dismiss_listener(lambda m, d: got.append(("dismiss", d)))
    iam.add_error_listener(lambda m, e: got.append(("error", e.name, e.description)))
    delegate = native.delegate
    assert isinstance(delegate, PyInAppMessagingDelegate)
    assert delegate is InAppMessaging._delegate

    message = fake_message()
    action = FakeAction.alloc().init()
    action.actionText = "Shop"
    action.actionURL = url("myapp://shop")
    delegate.impressionDetectedForMessage_(message)
    delegate.messageClicked_withAction_(message, action)
    delegate.messageDismissed_dismissType_(message, DismissType.USER_SWIPE)
    error = ObjCClass("NSError").errorWithDomain_code_userInfo_(
        IN_APP_MESSAGING_ERROR_DOMAIN,
        InAppMessagingErrorCode.IMAGE_DATA_INVALID,
        {"NSLocalizedDescription": "bad image"},
    )
    delegate.displayErrorForMessage_error_(message, error)
    assert got == [
        ("seen", "50% off"),
        ("click", Action("Shop", "myapp://shop")),
        ("dismiss", DismissType.USER_SWIPE),
        ("error", "IMAGE_DATA_INVALID", "bad image"),
    ]
    remove()
    remove()
    delegate.impressionDetectedForMessage_(message)
    assert len(got) == 4


CALLS = []


class FakeDisplayDelegate(NSObject):
    """Records what a custom display tells Firebase (in ``CALLS``)."""

    @objc_method
    def impressionDetectedForMessage_(self, message: objc_id) -> None:
        CALLS.append("impression")

    @objc_method
    def messageClicked_withAction_(self, message: objc_id, action: objc_id) -> None:
        native = objc_instance(action)
        CALLS.append(
            ("clicked", str(native.actionText), str(native.actionURL.absoluteString))
        )

    @objc_method
    def messageDismissed_dismissType_(self, message: objc_id, kind: c_long) -> None:
        CALLS.append(("dismissed", kind))

    @objc_method
    def displayErrorForMessage_error_(self, message: objc_id, error: objc_id) -> None:
        CALLS.append(("failed", objc_instance(error).code))


class FIRInAppMessagingAction(NSObject):
    """Stands in for the SDK's ``FIRInAppMessagingAction``."""

    actionText = objc_property()
    actionURL = objc_property()

    @objc_method
    def initWithActionText_actionURL_(self, text, link) -> objc_id:
        self.actionText = text
        self.actionURL = link
        return self


@pytest.fixture
def display(iam, monkeypatch):
    monkeypatch.setattr(module, "_is_main_thread", lambda: True)
    CALLS.clear()
    return iam


def test_python_display(display):
    iam, native = display
    shown = []

    def handler(message, delegate):
        shown.append(message)
        delegate.impression()
        delegate.impression()  # counted once
        delegate.clicked()
        with pytest.raises(RuntimeError):
            delegate.dismissed()

    iam.set_display(handler)
    component = native.messageDisplayComponent
    assert isinstance(component, PyInAppMessagingDisplay)
    component.displayMessage_displayDelegate_(
        fake_message(), FakeDisplayDelegate.alloc().init()
    )
    assert shown[0].title == "50% off"
    assert CALLS == [
        "impression",
        ("clicked", "Shop", "myapp://shop"),
    ]


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_python_display_dismiss_and_raise(display):
    iam, native = display
    iam.set_display(lambda m, d: d.dismissed(DismissType.AUTO))
    native.messageDisplayComponent.displayMessage_displayDelegate_(
        fake_message(), FakeDisplayDelegate.alloc().init()
    )

    def broken(message, delegate):
        raise KeyError("oops")

    # the error is printed (it happens in a call from Objective-C), and the
    # message fails, so Firebase does not wait for it forever
    iam.set_display(broken)
    native.messageDisplayComponent.displayMessage_displayDelegate_(
        fake_message(), FakeDisplayDelegate.alloc().init()
    )
    assert CALLS == [
        ("dismissed", DismissType.AUTO),
        ("failed", InAppMessagingErrorCode.UNSPECIFIED),
    ]


def test_set_display_none_and_default(display, monkeypatch):
    iam, native = display
    iam.set_display(None)
    assert native.messageDisplayComponent is None
    default = Recorder()
    monkeypatch.setattr(
        module,
        "objc_class",
        lambda name: (
            type("C", (), {"alloc": lambda: type("A", (), {"init": lambda: default})})
            if name == "FIRIAMDefaultDisplayImpl"
            else None
        ),
    )
    iam.use_default_display()
    assert native.messageDisplayComponent is default
    assert InAppMessaging._display_handler is None


def test_in_app_messaging_before_configure(monkeypatch):
    fake = type("FIRInAppMessaging", (), {"inAppMessaging": staticmethod(lambda: None)})
    monkeypatch.setattr(module, "objc_class", lambda name: fake)
    monkeypatch.setattr(InAppMessaging, "_shared", None)
    with pytest.raises(RuntimeError, match="configure"):
        InAppMessaging.in_app_messaging()
    native = Recorder()
    fake.inAppMessaging = staticmethod(lambda: native)
    assert InAppMessaging.in_app_messaging().native is native
