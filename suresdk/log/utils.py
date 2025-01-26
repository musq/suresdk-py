import logging
import traceback

from suresdk.utils import generate_traceback_from_exception_details

# Here we create a dummy LogRecord object by setting its first 7 arguments as "dummy".
# Then we filter out all the default fields from our received LogRecord object.
DEFAULT_LOG_RECORD_FIELDS = set(logging.LogRecord(*["dummy"] * 7).__dict__.keys()) | {
    "message"
}  # type: ignore


def extract_extra_fields(record: logging.LogRecord) -> dict:
    return {
        k: v for k, v in record.__dict__.items() if k not in DEFAULT_LOG_RECORD_FIELDS
    }


def uncaught_exception_logger(
    exc_type: BaseException, exc_value: Exception, tb: traceback.TracebackException
):
    exception_string = generate_traceback_from_exception_details(
        exc_type, exc_value, tb
    )
    # Raise to root logger where it will be consumed by the formatter attached to our handler
    logging.getLogger().critical(
        f"Uncaught exception: {repr(exc_value)}",
        extra={"stack_trace": exception_string},
    )
