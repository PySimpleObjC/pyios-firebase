import math

import pytest
from conftest import Recorder, fire, make_error

import pyios_firebase.analytics as analytics_module
from pyios_firebase.analytics import (
    Analytics,
    ConsentStatus,
    ConsentType,
    Event,
    Param,
    UserProperty,
)
from pyios_firebase.util import to_python


@pytest.fixture
def fir(monkeypatch):
    native = Recorder(returns={"appInstanceID": lambda: "app-1"})
    monkeypatch.setattr(analytics_module, "_analytics", lambda: native)
    return native


def test_names_match_the_sdk_headers():
    assert Event.ADD_TO_CART == "add_to_cart"
    assert Event.SCREEN_VIEW == "screen_view"
    assert Param.ITEMS == "items"
    assert Param.ITEM_ID == "item_id"
    assert UserProperty.SIGN_UP_METHOD == "sign_up_method"
    assert UserProperty.ALLOW_AD_PERSONALIZATION_SIGNALS == "allow_personalized_ads"
    count = sum(
        1
        for cls in (Event, Param, UserProperty)
        for name in vars(cls)
        if name.isupper()
    )
    assert count == 112


def test_log_event(fir):
    Analytics.log_event(
        Event.PURCHASE,
        {
            Param.CURRENCY: "EUR",
            Param.VALUE: 9.99,
            "quantity": 2,
            Param.ITEMS: [{Param.ITEM_ID: "sku-1", Param.PRICE: 9.99}],
        },
    )
    name, params = fir.last("logEventWithName_parameters_")
    assert name == "purchase"
    assert to_python(params) == {
        "currency": "EUR",
        "value": 9.99,
        "quantity": 2,
        "items": [{"item_id": "sku-1", "price": 9.99}],
    }
    Analytics.log_event("tutorial_done")
    assert fir.last("logEventWithName_parameters_") == ("tutorial_done", None)


@pytest.mark.parametrize(
    ("name", "params", "error", "message"),
    [
        ("", None, ValueError, "invalid event name"),
        ("1st", None, ValueError, "starting with a letter"),
        ("a-b", None, ValueError, "invalid event name"),
        ("x" * 41, None, ValueError, "1 to 40"),
        ("firebase_x", None, ValueError, "reserved"),
        ("first_open", None, ValueError, "reserved event name"),
        ("ok", {"flag": True}, TypeError, "no bool parameters"),
        ("ok", {"at": object()}, TypeError, "must be str, int or float"),
        ("ok", {"n": math.nan}, ValueError, "cannot log nan"),
        ("ok", {"ga_x": 1}, ValueError, "reserved"),
        ("ok", {f"p{i}": i for i in range(26)}, ValueError, "at most 25"),
        ("ok", {"items": [1]}, TypeError, "items must be dicts"),
    ],
)
def test_log_event_refuses_what_analytics_would_drop(fir, name, params, error, message):
    with pytest.raises(error, match=message):
        Analytics.log_event(name, params)
    assert not fir.calls


def test_screen_view(fir):
    Analytics.log_screen_view("Checkout", "CheckoutScreen", {"step": 2})
    name, params = fir.last()
    assert name == "screen_view"
    assert to_python(params) == {
        "screen_name": "Checkout",
        "screen_class": "CheckoutScreen",
        "step": 2,
    }


def test_user_properties_and_id(fir):
    Analytics.set_user_property("premium", "plan")
    assert fir.last() == ("premium", "plan")
    Analytics.set_user_property(None, "plan")
    with pytest.raises(ValueError, match="1 to 24"):
        Analytics.set_user_property("x", "p" * 25)
    with pytest.raises(ValueError, match="reserved"):
        Analytics.set_user_property("x", "user_id")
    with pytest.raises(ValueError, match="36"):
        Analytics.set_user_property("v" * 37, "plan")
    with pytest.raises(TypeError):
        Analytics.set_user_property(3, "plan")
    Analytics.set_user_id("u1")
    Analytics.set_user_id(None)
    with pytest.raises(ValueError):
        Analytics.set_user_id("")
    assert [c[0] for c in fir.calls][-2:] == ["setUserID_", "setUserID_"]


def test_settings_and_ids(fir, blocks):
    Analytics.set_analytics_collection_enabled(False)
    Analytics.set_session_timeout_interval(600)
    Analytics.reset_analytics_data()
    assert Analytics.app_instance_id() == "app-1"
    assert fir.calls[:3] == [
        ("setAnalyticsCollectionEnabled_", (False,)),
        ("setSessionTimeoutInterval_", (600.0,)),
        ("resetAnalyticsData", ()),
    ]
    got = []
    Analytics.session_id(lambda s, e: got.append((s, e)))
    fire(fir.block(), 1234, None)
    Analytics.session_id(lambda s, e: got.append((s, e)))
    fire(fir.block(), 0, make_error("collection disabled", 1, "com.google.analytics"))
    assert got[0] == (1234, None)
    assert got[1][0] is None and got[1][1].description == "collection disabled"
    assert not blocks


def test_default_parameters(fir):
    Analytics.set_default_event_parameters({"app_flavor": "pro", "old": None})
    assert to_python(fir.last()[0]) == {"app_flavor": "pro", "old": None}
    Analytics.set_default_event_parameters(None)
    assert fir.last() == (None,)
    with pytest.raises(TypeError):
        Analytics.set_default_event_parameters({"flag": False})


def test_consent(fir):
    Analytics.set_consent(
        {
            ConsentType.ANALYTICS_STORAGE: ConsentStatus.GRANTED,
            ConsentType.AD_STORAGE: ConsentStatus.DENIED,
        }
    )
    assert to_python(fir.last()[0]) == {
        "analytics_storage": "granted",
        "ad_storage": "denied",
    }
    with pytest.raises(ValueError, match="consent type"):
        Analytics.set_consent({"cookies": ConsentStatus.GRANTED})
    with pytest.raises(ValueError, match="consent status"):
        Analytics.set_consent({ConsentType.AD_STORAGE: "yes"})


def test_on_device_conversion(fir):
    Analytics.initiate_on_device_conversion_measurement(email_address="a@b.co")
    Analytics.initiate_on_device_conversion_measurement(hashed_phone_number=b"\x01")
    assert [c[0] for c in fir.calls] == [
        "initiateOnDeviceConversionMeasurementWithEmailAddress_",
        "initiateOnDeviceConversionMeasurementWithHashedPhoneNumber_",
    ]
    with pytest.raises(ValueError, match="exactly one"):
        Analytics.initiate_on_device_conversion_measurement()
    with pytest.raises(ValueError, match="exactly one"):
        Analytics.initiate_on_device_conversion_measurement(
            email_address="a@b.co", phone_number="+15555550100"
        )
