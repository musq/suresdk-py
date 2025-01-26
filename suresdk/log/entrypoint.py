import logging
import sys

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from .filters import AttachKeyValue
from .formatters import ConsoleFormatter
from .handlers import get_otlp_handler
from .utils import uncaught_exception_logger


def create_logger(
    name: str,
    env: str,
    resource: Resource | None = None,
    level: str = "INFO",
    debug: bool = False,
) -> logging.LoggerAdapter:
    if resource is None:
        resource = Resource.create()

    logging.captureWarnings(True)
    root_logger = logging.getLogger()

    # Setup console handler to stream logs in the terminal stdout
    console_handler = logging.StreamHandler()
    console_handler.name = "suresdk_console_handler"
    console_handler.setFormatter(ConsoleFormatter())

    if console_handler.name not in set(
        handler.name for handler in root_logger.handlers
    ):
        # Attach console_handler only once even if we call create_logger() multiple times
        root_logger.addHandler(console_handler)

    # Setup OTLP handler to send logs to an OTel Collector compatible sidecar
    if not debug:
        otlp_handler = get_otlp_handler(resource=resource)
        otlp_handler.name = "suresdk_otlp_handler"

        if otlp_handler.name not in set(
            handler.name for handler in root_logger.handlers
        ):
            # Attach otlp_handler only once even if we call create_logger() multiple times
            root_logger.addHandler(otlp_handler)

    assert root_logger.hasHandlers(), "Root logger must have at least one handler"

    for handler in root_logger.handlers:
        if service_namespace := resource.attributes.get(
            ResourceAttributes.SERVICE_NAMESPACE
        ):
            # Repo name
            handler.addFilter(
                AttachKeyValue("service_namespace", str(service_namespace))
            )

        if service_name := resource.attributes.get(ResourceAttributes.SERVICE_NAME):
            # Service name
            handler.addFilter(AttachKeyValue("service_name", str(service_name)))

        if service_version := resource.attributes.get(
            ResourceAttributes.SERVICE_VERSION
        ):
            # Repo git sha
            handler.addFilter(AttachKeyValue("service_version", str(service_version)))

        if service_instance_id := resource.attributes.get(
            ResourceAttributes.SERVICE_INSTANCE_ID
        ):
            # Service deployment task id
            handler.addFilter(
                AttachKeyValue("service_instance_id", str(service_instance_id))
            )

        handler.addFilter(AttachKeyValue("env", env))

    sys.excepthook = uncaught_exception_logger  # type: ignore

    logger = logging.getLogger(name)
    logger.setLevel(level.upper())

    body_logger = BodyLoggingAdapter(logger=logger)

    return body_logger


class BodyLoggingAdapter(logging.LoggerAdapter):
    """
    The purpose of this adapater over plain logging.Logger is only to make logging of
    "body" easier for developers. We use "body" to attach context to logs. Attaching
    context to logs is a very important and developer friendly feature, as it makes
    debugging easier.

    Normally (without BodyLoggingAdapter) we'd use "extra" with "body" dict nested inside it:
    LOG.info("Message", extra={"body": {"key1": "val1", "key2": "val2"}})

    However this becomes cumbersome and verbose for developers very soon. Plus, writing
    boilerplate code like `extra={"body": {}}` affects readability.

    So, if we use this logger, we can write the above log like this:
    LOG.info("Message", body={"key1": "val1", "key2": "val2"})

    This is easier to read and write.
    """

    def process(self, msg, kwargs):
        body = kwargs.pop("body", {})
        if body:
            # Make sure body is a dict
            assert isinstance(body, dict), f"body must be a dict: body={body}"

            extra = kwargs.get("extra", {})
            extra["body"] = extra.get("body", {}) | body
            kwargs["extra"] = extra

        return msg, kwargs
