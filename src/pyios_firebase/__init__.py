"""Use Firebase from Python on iOS, through Rubicon-ObjC.

One subpackage per Firebase product. Import only the ones you use: each one
needs its Firebase framework in the app.

- ``pyios_firebase.core``: ``configure()``
- ``pyios_firebase.analytics``: Google Analytics
- ``pyios_firebase.app_check``: App Check providers and tokens
- ``pyios_firebase.auth``: Firebase Authentication
- ``pyios_firebase.crashlytics``: Crashlytics
- ``pyios_firebase.database``: Realtime Database
- ``pyios_firebase.firestore``: Cloud Firestore
- ``pyios_firebase.functions``: Cloud Functions (HTTPS callables)
- ``pyios_firebase.messaging``: Cloud Messaging and notifications
- ``pyios_firebase.performance``: Performance Monitoring
- ``pyios_firebase.remote_config``: Remote Config
- ``pyios_firebase.storage``: Cloud Storage
- ``pyios_firebase.types``: types for your own annotations
"""

from .core import configure
from .types import FirebaseError, QueryDict

__all__ = ("FirebaseError", "QueryDict", "__version__", "configure")

__version__ = "0.2.0"
