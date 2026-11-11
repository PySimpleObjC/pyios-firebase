# Type hints

Every public function and method is typed, and `pyios_firebase.types` has the
shapes to annotate your own callbacks with:

```python
from pyios_firebase.firestore import QuerySnapshot
from pyios_firebase.types import FirebaseError


def on_cities(snapshot: QuerySnapshot | None, error: FirebaseError | None) -> None:
    if error is not None:
        print(error.code, error.description)  # int, str
        return
    assert snapshot is not None
    for doc in snapshot:                       # DocumentSnapshot
        print(doc.document_id, doc.data)       # str, dict[str, Any]
```

| Type | What it is |
|---|---|
| `FirebaseError` | Every callback error: `code`, `description`, `domain`, `underlying_error` |
| `auth.AuthError` | An Auth error: adds `name`, `email`, `updated_credential`, `cancelled`, `message` |
| `ResultCallback[T]` | `Callable[[T \| None, FirebaseError \| None], None]` |
| `ErrorCallback` | `Callable[[FirebaseError \| None], None]`, for writes |
| `FirestoreData` | `Mapping[str, Any]`: data you write |
| `ObjCObject` | An Objective-C object from Rubicon (typed `Any`) |

Errors and results are still dicts (`QueryDict`), so `error["code"]` and
`error.code` both work. The classes only tell the type checker which keys exist.

Type checkers also catch mistakes such as a callback with the wrong number of
arguments, a `DocumentReference` where a `DocumentSnapshot` is needed (query
cursors), or a transaction function whose return type does not match its
callback.

Rubicon itself has no type information, so Objective-C objects the library does
not wrap are typed `Any` (the `ObjCObject` alias).

