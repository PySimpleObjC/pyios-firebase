from ctypes import c_ulong
from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import Block, NSObject, ns_from_py, objc_property

from pyios_firebase.messaging import (
    MESSAGING_ERROR_DOMAIN,
    APNSTokenType,
    Messaging,
    MessagingErrorCode,
    notifications,
)
from pyios_firebase.messaging.messaging import PyMessagingDelegate
from pyios_firebase.messaging.notifications import (
    DEFAULT_ACTION,
    Notification,
    PresentationOptions,
    PyNotificationCenterDelegate,
)
from pyios_firebase.util import to_python


@pytest.fixture
def messaging():
    native = Recorder()
    native.APNSToken = None
    native.FCMToken = None
    native.isAutoInitEnabled = lambda: True
    native.isInstallationIdEnabled = False
    yield Messaging(native), native
    for listeners in Messaging._listeners.values():
        listeners.clear()
    Messaging._delegate = None


def test_token(messaging, blocks):
    messaging, native = messaging
    got = []
    messaging.token(lambda t, e: got.append((t, e)))
    fire(native.block("tokenWithCompletion_"), ns_from_py("fcm-1"), None)
    messaging.token(lambda t, e: got.append((t, e)))
    fire(
        native.block("tokenWithCompletion_"),
        None,
        make_error("no network", MessagingErrorCode.NETWORK, MESSAGING_ERROR_DOMAIN),
    )
    assert got[0] == ("fcm-1", None)
    assert got[1][0] is None and got[1][1].name == "NETWORK"
    assert not blocks


def test_properties(messaging):
    messaging, native = messaging
    assert messaging.fcm_token is None
    assert messaging.apns_token is None
    messaging.apns_token = b"\x01\x02"
    assert messaging.apns_token == b"\x01\x02"
    messaging.set_apns_token(b"\x03", APNSTokenType.SANDBOX)
    token, token_type = native.last("setAPNSToken_type_")
    assert bytes(to_python(token)) == b"\x03" and token_type == 1
    assert messaging.auto_init_enabled is True
    messaging.auto_init_enabled = False
    assert native.last("setAutoInitEnabled_") == (False,)
    assert messaging.installation_id_enabled is False


def test_topics(messaging, blocks):
    messaging, native = messaging
    messaging.subscribe_to_topic("news")
    messaging.unsubscribe_from_topic("/topics/sports.eu~1")
    assert native.calls[0][1][0] == "news"
    assert native.calls[1][1][0] == "sports.eu~1"
    for bad in ("", "a b", "a/b", "x" * 901):
        with pytest.raises(ValueError, match="invalid topic"):
            messaging.subscribe_to_topic(bad)
    with pytest.raises(TypeError):
        messaging.subscribe_to_topic(3)
    blocks.clear()


def test_registration_and_deletes(messaging, blocks):
    messaging, native = messaging
    errors = []
    messaging.register(errors.append)
    messaging.unregister()
    messaging.delete_token()
    messaging.delete_data()
    messaging.retrieve_fcm_token("123", lambda t, e: None)
    messaging.delete_fcm_token("123")
    assert [c[0] for c in native.calls] == [
        "registerWithCompletion_",
        "unregisterWithCompletion_",
        "deleteTokenWithCompletion_",
        "deleteDataWithCompletion_",
        "retrieveFCMTokenForSenderID_completion_",
        "deleteFCMTokenForSenderID_completion_",
    ]
    fire(native.block("registerWithCompletion_"), None)
    assert errors == [None]
    blocks.clear()


def test_listeners_get_what_the_delegate_gets(messaging):
    messaging, native = messaging
    tokens, registrations = [], []
    remove = messaging.add_token_listener(tokens.append)
    messaging.add_registration_listener(registrations.append)
    assert native.delegate is Messaging._delegate
    delegate = Messaging._delegate
    delegate.messaging_didReceiveRegistrationToken_(None, ns_from_py("fcm-2"))
    delegate.messaging_didReceiveRegistration_(None, ns_from_py("fid-1"))
    assert tokens == ["fcm-2"] and registrations == ["fid-1"]
    remove()
    remove()
    delegate.messaging_didReceiveRegistrationToken_(None, ns_from_py("fcm-3"))
    assert tokens == ["fcm-2"]
    assert isinstance(delegate, PyMessagingDelegate)


def test_app_did_receive_message(messaging):
    messaging, native = messaging
    native._returns["appDidReceiveMessage_"] = lambda: SimpleNamespace(status=1)
    assert messaging.app_did_receive_message({"gcm.message_id": "m1"}) == 1


# ---- notifications ----------------------------------------------------------------


class FakeContent(NSObject):
    title = objc_property()
    subtitle = objc_property()
    body = objc_property()
    badge = objc_property()
    userInfo = objc_property()
    categoryIdentifier = objc_property()
    threadIdentifier = objc_property()


class FakeRequest(NSObject):
    identifier = objc_property()
    content = objc_property()


class FakeNotification(NSObject):
    request = objc_property()
    date = objc_property()


class FakeSettings(NSObject):
    authorizationStatus = objc_property(c_ulong)


class FakeResponse(NSObject):
    notification = objc_property()
    actionIdentifier = objc_property()


def fake_notification():
    content = FakeContent.alloc().init()
    content.title = "Sale"
    content.body = "50% off"
    content.badge = ns_from_py(3)
    content.userInfo = ns_from_py(
        {"aps": {"alert": {"title": "Sale"}}, "gcm.message_id": "m1", "screen": "shop"}
    )
    request = FakeRequest.alloc().init()
    request.identifier = "req-1"
    request.content = content
    notification = FakeNotification.alloc().init()
    notification.request = request
    return notification


def test_notification_from_native():
    notification = Notification.from_native(fake_notification())
    assert notification.title == "Sale" and notification.body == "50% off"
    assert notification.subtitle == "" and notification.badge == 3
    assert notification.data["screen"] == "shop"
    assert notification.message_id == "m1"
    assert notification.date is None


@pytest.fixture
def handlers(monkeypatch):
    center = SimpleNamespace(delegate=None)
    monkeypatch.setattr(notifications, "_center", lambda: center)
    yield center
    notifications._Handlers.on_foreground = None
    notifications._Handlers.on_open = None


def test_foreground_and_open_handlers(handlers):
    shown, opened, answers = [], [], []
    notifications.set_handlers(
        on_foreground=lambda n: shown.append(n) or PresentationOptions.BANNER,
        on_open=lambda n, action: opened.append((n.identifier, action)),
    )
    delegate = handlers.delegate
    assert isinstance(delegate, PyNotificationCenterDelegate)

    present = Block(lambda options: answers.append(options), None, c_ulong)
    delegate.userNotificationCenter_willPresentNotification_withCompletionHandler_(
        None, fake_notification(), present
    )
    assert shown[0].title == "Sale"
    assert answers == [PresentationOptions.BANNER]

    response = FakeResponse.alloc().init()
    response.notification = fake_notification()
    response.actionIdentifier = DEFAULT_ACTION
    done = Block(lambda: answers.append("done"), None)
    delegate.userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(
        None, response, done
    )
    assert opened == [("req-1", DEFAULT_ACTION)]
    assert answers[-1] == "done"


def test_default_presentation(handlers):
    answers = []
    notifications.set_handlers(default_presentation=PresentationOptions.LIST)
    present = Block(lambda options: answers.append(options), None, c_ulong)
    handlers.delegate.userNotificationCenter_willPresentNotification_withCompletionHandler_(
        None, fake_notification(), present
    )
    assert answers == [PresentationOptions.LIST]


def test_permission_and_status(monkeypatch, blocks):
    center = Recorder()
    monkeypatch.setattr(notifications, "_center", lambda: center)
    got = []
    notifications.request_permission(
        notifications.AuthorizationOptions.ALERT
        | notifications.AuthorizationOptions.SOUND,
        lambda granted, error: got.append((granted, error)),
    )
    options, block = center.last()
    assert options == 6
    fire(block, True, None)
    notifications.authorization_status(got.append)
    settings = FakeSettings.alloc().init()
    settings.authorizationStatus = 2
    fire(center.block(), settings)
    assert got == [(True, None), 2]
    assert not blocks
