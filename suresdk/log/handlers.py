import logging

import flatten_dict
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.util.types import Attributes


def get_otlp_handler(resource: Resource) -> LoggingHandler:
    # We can provide resource details to the log handler in 3 ways:
    # - Directly here as LoggerProvider(resource=Resource.create({"service.name": "dummy_service", "service.namespace": "dummy_repo", "service.version": "xxx", "service.instance.id": "xxx"}))
    # - Command params: opentelemetry-instrument --service_name "dummy_service" --resource_attributes "service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" python app.py
    # - Env variables: OTEL_SERVICE_NAME="dummy_service" OTEL_RESOURCE_ATTRIBUTES="service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" opentelemetry-instrument python app.py
    otlp_logger_provider = LoggerProvider(resource=resource)

    # CRITICAL: Do not miss to set the LoggerProvider globally!
    set_logger_provider(otlp_logger_provider)

    otlp_logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            # endpoint can also be configured in 3 ways:
            # - Directly here as OTLPLogExporter(endpoint="localhost:4317")
            # - Or, the specific env variable: OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
            # - Or, the generic env variable: OTEL_EXPORTER_OTLP_ENDPOINT
            # NOTE: Prefer env variables to configure endpoint here
            exporter=OTLPLogExporter(),
            # Amount of time to wait to collect a batch of logs.
            # OTLPLogExporter will export the batch of logs to the endpoint when either:
            # - The batch has reached the maximum size
            # - Or, when this amount of time has passed waiting for the batch to be full
            # - Or, just before exiting the Python interpreter
            schedule_delay_millis=3000,
        )
    )

    # Uncomment the following snippet to debug OTLP logs handler. This will
    # print OTLP logs in the console.
    otlp_logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            exporter=ConsoleLogExporter(), schedule_delay_millis=3000
        )
    )

    otlp_handler = BodyLoggingHandler(logger_provider=otlp_logger_provider)

    return otlp_handler


class BodyLoggingHandler(LoggingHandler):
    """This handler exists to modify the underlying formatter, so we are able
    to capture contextual information added to logs in the 'body' dict."""

    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> Attributes:
        # NOTE: We are converting the type of attributes from Attributes (i.e.
        # collections.abc.Mapping) to dict to reduce typing errors below. If it
        # causes errors in the future, we'll avoid converting to dict, and
        # instead allow typing errors below.
        attributes = dict(LoggingHandler._get_attributes(record) or {})

        # CRITICAL: Remove these attributes from OTLP Handler because they are
        # explicitly added to all the handlers in create_logger() function.
        # OTLP Handler automatically attaches them from the resource
        # attributes, so removing them here avoids duplication.
        attributes.pop("service_namespace", None)
        attributes.pop("service_name", None)
        attributes.pop("service_version", None)
        attributes.pop("service_instance_id", None)

        body: dict | None = attributes.get("body")  # type: ignore

        if body is not None:
            # Make sure body is a dict
            assert isinstance(body, dict), f"body must be a dict: body={body}"

            del attributes["body"]

            # Convert {"body": {"abc": 123, 78.9: 0.21, "x.y": {"q": 1, 2: {"w.z": "man", 3: "zebra"}}}} to
            # {"body.abc": 123, "body.78.9": 0.21, "body.x.y.q": 1, "body.x.y.2.w.z": "man", "body.x.y.2.3": "zebra"}
            attributes |= flatten_dict.flatten(d={"body": body}, reducer="dot")

        return attributes
