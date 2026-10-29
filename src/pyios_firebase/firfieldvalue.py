from rubicon.objc import ObjCClass, at

FIRFieldValue = ObjCClass("FIRFieldValue")


class FieldValue:
    @staticmethod
    def field_value_for_delete():
        return FIRFieldValue.fieldValueForDelete()

    @staticmethod
    def field_value_for_server_timestamp():
        return FIRFieldValue.fieldValueForServerTimestamp()

    @staticmethod
    def field_value_for_array_union(elements):
        return FIRFieldValue.fieldValueForArrayUnion_(at(list(elements)))

    @staticmethod
    def field_value_for_array_remove(elements):
        return FIRFieldValue.fieldValueForArrayRemove_(at(list(elements)))

    @staticmethod
    def field_value_for_integer_increment(value):
        return FIRFieldValue.fieldValueForIntegerIncrement_(int(value))

    @staticmethod
    def field_value_for_double_increment(value):
        return FIRFieldValue.fieldValueForDoubleIncrement_(float(value))
