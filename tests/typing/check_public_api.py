"""Type-checked, never run: how an app uses the library, as editors see it.

    uv run mypy tests/typing

``assert_type`` lines check what the checker infers. Lines with
``# type: ignore[...]`` are mistakes the types must catch: if one stops being
an error, mypy (strict, warn_unused_ignores) fails on the unused ignore.
"""

from datetime import UTC, datetime
from typing import Any, assert_type

from pyios_firebase.firestore import (
    AggregateField,
    AggregateQuerySnapshot,
    CollectionReference,
    DocumentChange,
    DocumentReference,
    DocumentSnapshot,
    FieldValue,
    Filter,
    FIRAggregateSource,
    Firestore,
    ListenerRegistration,
    Query,
    QuerySnapshot,
    Transaction,
    WriteBatch,
)
from pyios_firebase.types import FirebaseError


def firestore_usage() -> None:
    db = Firestore.firestore()
    cities = db.collection_with_path("cities")
    assert_type(cities, CollectionReference)
    sf = cities.document_with_path("SF")
    assert_type(sf, DocumentReference)
    assert_type(db.collection_group_with_id("landmarks"), Query)
    assert_type(
        cities.query_where_field_is_greater_than("at", datetime.now(UTC)), Query
    )
    assert_type(cities.parent, DocumentReference | None)

    def on_city(snapshot: DocumentSnapshot | None, error: FirebaseError | None) -> None:
        if error is not None:
            assert_type(error.code, int)
            assert_type(error.description, str)
            return
        assert snapshot is not None
        assert_type(snapshot.data, dict[str, Any])
        assert_type(snapshot.exists, bool)

    def on_cities(snapshot: QuerySnapshot | None, error: FirebaseError | None) -> None:
        assert snapshot is not None
        assert_type(snapshot[0], DocumentSnapshot)
        assert_type(snapshot[1:], list[DocumentSnapshot])
        for doc in snapshot:
            assert_type(doc, DocumentSnapshot)
        for change in snapshot.document_changes:
            assert_type(change, DocumentChange)
            if change.type == DocumentChange.ADDED:
                pass

    sf.get_document(on_city)
    cities.get_documents(on_cities)
    listener = cities.add_snapshot_listener(on_cities)
    assert_type(listener, ListenerRegistration)
    listener.remove()

    sf.set_data({"at": datetime.now(UTC), "n": None}, merge=True)
    sf.update_data({"visits": FieldValue.field_value_for_integer_increment(1)})
    sf.delete_document(lambda error: print(error.description if error else "deleted"))
    assert_type(cities.add_document_with_data({"name": "x"}), DocumentReference)

    batch = db.batch().set_data({}, sf).delete_document(sf)
    assert_type(batch, WriteBatch)
    batch.commit()

    cities.query_where_filter(
        Filter.or_filter_with_filters([Filter.filter_where_field_is_equal_to("a", 1)])
    )

    def update(transaction: Transaction) -> int:
        population: int = transaction.get_document(sf).get("population")
        transaction.update_data({"population": population + 1}, sf)
        return population + 1

    def on_done(result: int | None, error: FirebaseError | None) -> None:
        pass

    db.run_transaction(update, on_done)

    def on_count(
        snapshot: AggregateQuerySnapshot | None, error: FirebaseError | None
    ) -> None:
        assert snapshot is not None
        assert_type(snapshot.count, int)
        avg = snapshot.value_for_aggregate_field(
            AggregateField.aggregate_field_for_count()
        )
        assert_type(avg, int | float | None)

    cities.count.aggregation_with_source(FIRAggregateSource.Server, on_count)


def firestore_mistakes() -> None:
    db = Firestore.firestore()
    sf = db.document_with_path("cities/SF")

    def wrong_arity(snapshot: DocumentSnapshot | None) -> None: ...

    sf.get_document(wrong_arity)  # type: ignore[arg-type]
    sf.set_data(["not", "a", "mapping"])  # type: ignore[arg-type]
    sf.update_data({"a": 1}, "not a callback")  # type: ignore[arg-type]
    db.collection_with_path(42)  # type: ignore[arg-type]
    # query cursors need a DocumentSnapshot, not a reference
    db.collection_with_path("c").query_starting_after_document(sf)  # type: ignore[arg-type]

    def on_done(result: str | None, error: FirebaseError | None) -> None: ...

    def update(transaction: Transaction) -> int:
        return 1

    # the result type of update_fn must match the callback
    db.run_transaction(update, on_done)  # type: ignore[misc]


def auth_usage() -> None:
    from pyios_firebase.auth import (
        ActionCodeSettings,
        Auth,
        AuthDataResult,
        AuthError,
        AuthErrorCode,
        AuthStateListener,
        EmailAuthProvider,
        IDTokenResult,
        OAuthCredential,
        OAuthProvider,
        User,
        current_user,
        sign_out,
    )
    from pyios_firebase.auth.apple import AppleSignInResult, start_apple_sign_in
    from pyios_firebase.auth.google import start_google_sign_in

    auth = Auth.auth()
    assert_type(auth.current_user, User | None)
    assert_type(current_user(), User | None)
    assert_type(sign_out(), AuthError | None)

    def on_signed_in(result: AuthDataResult | None, error: AuthError | None) -> None:
        if error is not None:
            assert_type(error.code, int)
            assert_type(error.cancelled, bool)
            if error.code == AuthErrorCode.EMAIL_ALREADY_IN_USE:
                pass
            return
        assert result is not None
        user = result.user
        assert_type(user, User)
        assert_type(user.uid, str | None)
        assert_type(user.is_anonymous, bool)

        def on_token(token: IDTokenResult | None, error: AuthError | None) -> None:
            assert token is not None
            assert_type(token.claims, dict[str, Any])
            assert_type(token.expiration_date, datetime)

        user.get_id_token_result(on_token, force_refresh=True)
        user.update_profile(display_name="Ada")
        user.update_profile(None, photo_url=None)

    auth.sign_in_with_email_password("a@b.c", "pw", on_signed_in)
    auth.create_user_with_email_password("a@b.c", "pw", on_signed_in)
    auth.sign_in_anonymously(on_signed_in)
    auth.sign_in_with_credential(
        EmailAuthProvider.credential("a@b.c", "pw"), on_signed_in
    )
    auth.send_sign_in_link(
        "a@b.c", ActionCodeSettings(url="https://x", handle_code_in_app=True)
    )
    assert_type(
        OAuthProvider.credential("microsoft.com", id_token="t"), OAuthCredential
    )
    listener = auth.add_state_did_change_listener(lambda user: None)
    assert_type(listener, AuthStateListener)
    listener.remove()

    start_google_sign_in(on_signed_in)

    def on_apple(result: AppleSignInResult | None, error: AuthError | None) -> None:
        if result is not None:
            assert_type(result.first_name, str)

    start_apple_sign_in(on_apple)


def auth_mistakes() -> None:
    from pyios_firebase.auth import ActionCodeSettings, Auth, User

    auth = Auth.auth()

    def one_argument(result: object) -> None: ...

    auth.sign_in_anonymously(one_argument)  # type: ignore[arg-type]
    auth.sign_in_with_credential("not a credential", None)  # type: ignore[arg-type]
    auth.send_sign_in_link("a@b.c", {"url": "https://x"})  # type: ignore[arg-type]
    # profile fields are keyword-only
    User().update_profile(None, "Ada")  # type: ignore[call-arg]
    ActionCodeSettings(url=42)  # type: ignore[arg-type]
