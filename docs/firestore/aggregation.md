# Aggregation

Count, sum and average documents **on the server**: the documents are not
downloaded, and you pay one read per batch of up to 1000 index entries instead
of one read per document.

## Count

```python
from pyios_firebase.firestore import FIRAggregateSource


def on_count(snapshot, error):
    if error is None:
        print("Cities in CA:", snapshot.count)


db.collection_with_path("cities") \
    .query_where_field_is_equal_to("state", "CA") \
    .count \
    .aggregation_with_source(FIRAggregateSource.Server, on_count)
```

## Sum and average

```python
from pyios_firebase.firestore import AggregateField, FIRAggregateSource

count = AggregateField.aggregate_field_for_count()
total = AggregateField.aggregate_field_for_sum_of_field("population")
average = AggregateField.aggregate_field_for_average_of_field("population")


def on_stats(snapshot, error):
    if error is not None:
        return
    print("Cities:", snapshot.value_for_aggregate_field(count))
    print("People:", snapshot.value_for_aggregate_field(total))
    print("Average:", snapshot.value_for_aggregate_field(average))


db.collection_with_path("cities") \
    .aggregate([count, total, average]) \
    .aggregation_with_source(FIRAggregateSource.Server, on_stats)
```

Up to five aggregations in one request.

## What the values mean

| Aggregation | Result | Documents counted |
|---|---|---|
| Count | `int` | Every document the query matches |
| Sum | `int`, or `float` if any value is a `float` | Those where the field is a number |
| Average | `float`, or `None` when no document has the field | Those where the field is a number |

Aggregations need the server: offline, they fail. They work with every
filter, and with [collection group](reading.md#collection-group-queries)
queries.
