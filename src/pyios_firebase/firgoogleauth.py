from collections.abc import Callable

from rubicon.objc import Block, ObjCClass, ObjCInstance
from rubicon.objc.runtime import objc_id

from .util import QueryDict

GIDConfiguration = ObjCClass("GIDConfiguration")
GIDSignIn = ObjCClass("GIDSignIn")
FIRApp = ObjCClass("FIRApp")
FIRGoogleAuthProvider = ObjCClass("FIRGoogleAuthProvider")
UIApplication = ObjCClass("UIApplication")
NSURL = ObjCClass("NSURL")
FIRAuth = ObjCClass("FIRAuth")


def on_gid_signin_handle_url_kivy(_, filename, *__):
    url_string = filename.decode("utf-8") if isinstance(filename, bytes) else filename
    print("openURL called:", url_string)
    url = NSURL.URLWithString_(url_string)
    GIDSignIn.sharedInstance.handleURL(url)


_callback: Callable[[QueryDict | dict, bool], None] | None = lambda *args: None


def get_root_view_controller():
    window = UIApplication.sharedApplication.keyWindow
    return window.rootViewController


@Block
def on_firebase_sign_in_done(auth_result_ptr: objc_id, error_ptr: objc_id) -> None:
    auth_result = ObjCInstance(auth_result_ptr) if auth_result_ptr else None
    error = ObjCInstance(error_ptr) if error_ptr else None
    print(error, auth_result)

    if error is not None:
        underlying = error.userInfo.objectForKey_("NSUnderlyingError")
        if underlying is not None:
            print("Underlying error:", underlying)
        error_msg = QueryDict(
            {
                "code": error.code,
                "description": error.localizedDescription,
                "underlying_error": underlying,
            }
        )
        _callback(error_msg, True)
        return

    if auth_result is None:
        return

    # User signed in. Get the user data from the FIRUser object
    user = auth_result.user
    user = QueryDict({"uid": user.uid, "email": user.email})
    _callback(user, False)


@Block
def on_sign_in_complete(result_ptr: objc_id, error_ptr: objc_id) -> None:
    # Turn the raw pointers into Python objects (or None)
    error = ObjCInstance(error_ptr) if error_ptr else None

    if error is None:
        result = ObjCInstance(result_ptr)
        id_token = result.user.idToken.tokenString
        access_token = result.user.accessToken.tokenString

        credential = FIRGoogleAuthProvider.credentialWithIDToken_accessToken_(
            id_token, access_token
        )
        FIRAuth.auth().signInWithCredential_completion_(
            credential, on_firebase_sign_in_done
        )
    else:
        print("Google sign-in error:", error.localizedDescription)
        underlying = error.userInfo.objectForKey_("NSUnderlyingError")
        if underlying is not None:
            print("Underlying error:", underlying)
        error_msg = QueryDict(
            {
                "code": error.code,
                "description": error.localizedDescription,
                "underlying_error": underlying,
            }
        )
        _callback(error_msg, True)


def start_google_sign_in(callback: Callable[[QueryDict | dict, bool], None]):
    global _callback
    _callback = callback
    client_id = FIRApp.defaultApp().options.clientID
    config = GIDConfiguration.alloc().initWithClientID_(client_id)
    GIDSignIn.sharedInstance.configuration = config

    GIDSignIn.sharedInstance.signInWithPresentingViewController_completion_(
        get_root_view_controller(), on_sign_in_complete
    )
