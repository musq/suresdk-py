import json
import logging
from typing import Any

from ..utils import generate_traceback_from_exception_details
from ..utils.serde import serialize
from .utils import extract_extra_fields


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        logger = record.name
        level = record.levelname
        timestamp = self.formatTime(record, "%H:%M:%S")
        message = record.getMessage()
        funcname = f"{record.module}.{record.funcName}:{record.lineno}"

        extra_fields = extract_extra_fields(record)
        extra_txt = " ".join([f"{k}={v}" for k, v in extra_fields.items()])

        log_line = f"[{level}] -- {timestamp} -- @{logger} :: (#{funcname}) :: {message} [{extra_txt}]"

        # If we are logging an exception, and exc_info, & exc_info[0] (i.e.
        # exc_info.exc_type) are present for this log record, then we also attach the
        # prettified stack trace in log.
        #
        # Case 1: We log an exception in except block => Attach stack trace
        # > Here, exc_info is not None, exc_info[0] is not None
        # try:
        #     x = 1/0
        # except Exception:
        #     logging.exception("Exception occurred")
        #
        # Case 2: We log an exception outside except block => Do not attach stack trace
        # > Here, exc_info is not None, exc_info[0] is None
        # logging.exception("Error occurred")
        #
        # Case 3: We log info, warning, error => Do not attach stack trace
        # > Here, exc_info is None
        # logging.error("Error occurred")
        # logging.warning("Warning encountered")
        # logging.info("General information")

        if record.exc_info and record.exc_info[0]:
            stack_trace = generate_traceback_from_exception_details(*record.exc_info)
            log_line += f"\n{stack_trace}"

        return log_line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        json_dict: dict[str, Any] = {}

        # Refer to ConsoleFormatter for explanation of this condition
        if record.exc_info and record.exc_info[0]:
            json_dict["stack_trace"] = generate_traceback_from_exception_details(
                *record.exc_info
            )

        json_dict["timestamp"] = record.created
        json_dict["level"] = record.levelname
        json_dict["logger"] = record.name
        json_dict["message"] = record.getMessage()
        json_dict["path"] = f"{record.pathname}:{record.funcName}:{record.lineno}"
        json_dict["process"] = f"{record.processName} <{record.process}>"
        json_dict["thread"] = f"{record.threadName} <{record.thread}>"

        json_dict.update(extract_extra_fields(record))

        # if "body" in json_dict:
        #     body = json_dict["body"]
        #     # Make sure body is a dict
        #     assert isinstance(body, dict), f"body must be a dict: body={body}"

        payload = json.dumps(serialize(json_dict))

        return f"payload: {payload}"
