from rubicon.objc import ObjCClass

FIRFilter = ObjCClass("FIRFilter")


class Filter:
    def __init__(self, filter_):
        self._filter = filter_

    # ---- single-field filters ----

    @staticmethod
    def filter_where_field_is_equal_to(field, value):
        return Filter(FIRFilter.filterWhereField_isEqualTo_(field, value))

    @staticmethod
    def filter_where_field_is_not_equal_to(field, value):
        return Filter(FIRFilter.filterWhereField_isNotEqualTo_(field, value))

    @staticmethod
    def filter_where_field_is_less_than(field, value):
        return Filter(FIRFilter.filterWhereField_isLessThan_(field, value))

    @staticmethod
    def filter_where_field_is_less_than_or_equal_to(field, value):
        return Filter(FIRFilter.filterWhereField_isLessThanOrEqualTo_(field, value))

    @staticmethod
    def filter_where_field_is_greater_than(field, value):
        return Filter(FIRFilter.filterWhereField_isGreaterThan_(field, value))

    @staticmethod
    def filter_where_field_is_greater_than_or_equal_to(field, value):
        return Filter(FIRFilter.filterWhereField_isGreaterThanOrEqualTo_(field, value))

    @staticmethod
    def filter_where_field_array_contains(field, value):
        return Filter(FIRFilter.filterWhereField_arrayContains_(field, value))

    @staticmethod
    def filter_where_field_array_contains_any(field, values):
        return Filter(FIRFilter.filterWhereField_arrayContainsAny_(field, values))

    @staticmethod
    def filter_where_field_in(field, values):
        return Filter(FIRFilter.filterWhereField_in_(field, values))

    @staticmethod
    def filter_where_field_not_in(field, values):
        return Filter(FIRFilter.filterWhereField_notIn_(field, values))

    # ---- combine filters ----

    @staticmethod
    def or_filter_with_filters(filters):
        return Filter(FIRFilter.orFilterWithFilters_([f._filter for f in filters]))

    @staticmethod
    def and_filter_with_filters(filters):
        return Filter(FIRFilter.andFilterWithFilters_([f._filter for f in filters]))
