import traceback


def generate_traceback_from_exception_details(exc_type, exc_value, tb) -> str:
    return "".join(traceback.format_exception(exc_type, exc_value, tb))


def generate_traceback(exception: Exception) -> str:
    return generate_traceback_from_exception_details(
        type(exception), exception, exception.__traceback__
    )
