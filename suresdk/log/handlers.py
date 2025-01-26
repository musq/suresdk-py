from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, set_logger_provider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


def get_otlp_handler(resource: Resource | None) -> LoggingHandler:
    # We can provide resource details to the log handler in 3 ways:
    # - Directly here as LoggerProvider(resource=Resource.create({"service.name": "dummy_service", "service.namespace": "dummy_repo", "service.version": "xxx", "service.instance.id": "xxx"}))
    # - Command params: opentelemetry-instrument --service_name "dummy_service" --resource_attributes "service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" python app.py
    # - Env variables: OTEL_SERVICE_NAME="dummy_service" OTEL_RESOURCE_ATTRIBUTES="service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" opentelemetry-instrument python app.py
    if resource is None:
        otlp_logger_provider = LoggerProvider()
    else:
        otlp_logger_provider = LoggerProvider(resource=resource)

    # CRITICAL: Do not miss to set the LoggerProvider globally!
    set_logger_provider(otlp_logger_provider)

    # otlp_logger_provider.add_log_record_processor(
    #     BatchLogRecordProcessor(
    #         # endpoint can also be configured in 3 ways:
    #         # - Directly here as OTLPLogExporter(endpoint="localhost:4317")
    #         # - Or, the specific env variable: OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
    #         # - Or, the generic env variable: OTEL_EXPORTER_OTLP_ENDPOINT
    #         # NOTE: Prefer env variables to configure endpoint here
    #         exporter=OTLPLogExporter(),
    #         # Amount of time to wait to collect a batch of logs.
    #         # OTLPLogExporter will export the batch of logs to the endpoint when either:
    #         # - The batch has reached the maximum size
    #         # - Or, when this amount of time has passed waiting for the batch to be full
    #         # - Or, just before exiting the Python interpreter
    #         schedule_delay_millis=3000,
    #     )
    # )

    # Uncomment the following snippet to debug OTLP logs handler. This will
    # print OTLP logs in the console.
    otlp_logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            exporter=ConsoleLogExporter(), schedule_delay_millis=3000
        )
    )

    otlp_handler = LoggingHandler(logger_provider=otlp_logger_provider)

    return otlp_handler
