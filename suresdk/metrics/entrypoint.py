import logging

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

_logger = logging.getLogger(__name__)


def create_meter(
    name: str, env: str, resource: Resource | None = None, debug: bool = False
) -> Meter:
    _logger.info("Trying to create an OTLP Meter to send metrics")

    # We can provide resource details to the meter provider in 3 ways:
    # - Directly here as resource=Resource.create({"service.name": "dummy_service", "service.namespace": "dummy_repo", "service.version": "xxx", "service.instance.id": "xxx"})
    # - Command params: opentelemetry-instrument --service_name "dummy_service" --resource_attributes "service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" python app.py
    # - Env variables: OTEL_SERVICE_NAME="dummy_service" OTEL_RESOURCE_ATTRIBUTES="service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" opentelemetry-instrument python app.py
    # NOTE: Prefer env variables to configure resource here

    if resource is None:
        resource = Resource.create()

    metric_readers = []
    if not debug:
        otlp_reader = PeriodicExportingMetricReader(
            # OTLP endpoint can be configured in 3 ways:
            # - Directly here as OTLPMetricExporter(endpoint="localhost:4317")
            # - Or, the specific env variable: OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
            # - Or, the generic env variable: OTEL_EXPORTER_OTLP_ENDPOINT
            # NOTE: Prefer env variables to configure endpoint here
            exporter=OTLPMetricExporter(),
            # Amount of time to wait to collect a batch of metrics.
            # PeriodicExportingMetricReader will export the batch of metrics to the endpoint when either:
            # - The batch has reached the maximum size
            # - Or, when this amount of time has passed waiting for the batch to be full
            # - Or, just before exiting the Python interpreter
            export_interval_millis=2500,
        )
        metric_readers.append(otlp_reader)

        # Uncomment the following snippet to debug OTLP metrics. This will
        # print OTLP metrics in the console.
        # from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        #
        # console_reader = PeriodicExportingMetricReader(
        #     exporter=ConsoleMetricExporter(),
        #     export_interval_millis=2500,
        # )
        # metric_readers.append(console_reader)

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)

    # CRITICAL: Do not miss to set the MeterProvider globally!
    # NOTE: set_meter_provider(...) here is redundant if we run this service
    # via opentelemetry-instrument. This is because opentelemetry-instrument
    # automatically initializes a MeterProvider and sets it globally using
    # set_meter_provider(...). Since the global meter provider can only be set
    # once via set_meter_provider(), and opentelemetry-instrument already sets
    # it, the following call to set_meter_provider() becomes redundant. Please
    # BEWARE that this means suresdk's MeterProvider is not set globally. So
    # you should use the meter provider created here to create your meters, and
    # don't rely on get_meter_provider().get_meter(...) to get meters as it will
    # use the wrong MeterProvider (the one set by opentelemetry-instrument).
    set_meter_provider(meter_provider)

    # TODO: Add support for "env=..." label
    meter = meter_provider.get_meter(name=name)

    _logger.info("OTLP Meter created successfully")

    return meter
