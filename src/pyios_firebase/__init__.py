"""Use Firebase from Python on iOS, through Rubicon-ObjC.

One subpackage per Firebase product. Import only the ones you use: each one
needs its Firebase framework in the app.

- ``pyios_firebase.core``: ``configure()``
- ``pyios_firebase.firestore``: Cloud Firestore
- ``pyios_firebase.types``: types for your own annotations

App Check, Auth and Google Sign-In are still the 0.1 modules
(``firappcheck``, ``firuser``, ``firgoogleauth``) until they move to
their own subpackages.
"""

from .core import configure
from .types import FirebaseError, QueryDict

__all__ = ("FirebaseError", "QueryDict", "__version__", "configure")

__version__ = "0.2.0"
