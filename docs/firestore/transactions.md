# Transactions and batches

Two ways to make several writes **atomic** (all of them happen, or none):

| | Reads | Offline | Use it to |
|---|---|---|---|
| **Batch** | No | Yes: queued, sent later | Write several documents together |
| **Transaction** | Yes, first | No: needs the server | Write from the current value (counters, transfers, unique names) |

## Write batches

```python
cities = db.collection_with_path("cities")

batch = db.batch()
batch.set_data({"name": "New York City"}, cities.document_with_path("NYC"))
batch.update_data({"population": 1_000_000}, cities.document_with_path("SF"))
batch.delete_document(cities.document_with_path("LA"))
batch.commit(on_committed)


def on_committed(error):
    print("Saved" if error is None else error.description)
```

- A batch holds up to **500** writes.
- Use a batch once: make a new one for the next writes.
- `set_data` in a batch takes `merge=True` too, and every value is converted
  like in a normal write; field values (increments, server timestamps) work.

## Transactions

A transaction reads documents, then writes based on what it read. If another
client changes those documents before the commit, Firestore runs the
function **again** with the new data.

```python
from pyios_firebase.firestore import TransactionException

sf = db.document_with_path("cities/SF")


def add_resident(transaction):
    snapshot = transaction.get_document(sf)
    population = snapshot.get("population")
    if not isinstance(population, int):
        raise TransactionException("SF has no population")
    if population >= 1_000_000:
        raise TransactionException("SF is full")

    transaction.update_data({"population": population + 1}, sf)
    return population + 1          # given to the callback


def on_done(result, error):
    if error is not None:
        print("Transaction failed:", error.description)
    else:
        print("Population is now", result)


db.run_transaction(add_resident, on_done)
```

### Rules

- **Reads first.** Do every `transaction.get_document(...)` before any write
  (`set_data`, `update_data`, `delete_document`).
- **No side effects.** The function can run several times: do not change the
  screen or your app's state inside it. Do that in the callback.
- **Return what you need.** The function's return value (any Python object) is
  the callback's `result`.
- **Raise to stop.** Raise any exception to abort: nothing is written, and the
  callback gets an error whose `description` is the exception's message.
  `TransactionException` is there for that, but any exception works.
- **Online only.** A transaction needs the server; offline, it fails.

### Example: a unique username

```python
def claim_username(uid, name):
    taken = db.document_with_path(f"usernames/{name}")
    user = db.document_with_path(f"users/{uid}")

    def claim(transaction):
        if transaction.get_document(taken).exists:
            raise TransactionException(f"{name} is taken")
        transaction.set_data({"uid": uid}, taken)
        transaction.update_data({"username": name}, user)
        return name

    db.run_transaction(claim, on_claimed)
```

### Transactions or increments?

To add to a counter, `FieldValue.field_value_for_integer_increment(n)` is
simpler and works offline. Use a transaction when the new value depends on
more than a simple sum (a maximum, a check, several documents).
