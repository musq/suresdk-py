import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
from opentelemetry.trace import Tracer, set_tracer_provider

_logger = logging.getLogger(__name__)


def create_tracer(
    name: str, env: str, resource: Resource | None = None, debug: bool = False
) -> Tracer:
    _logger.info("Trying to create an OTLP Tracer to send traces")

    # We can provide resource details to the tracer provider in 3 ways:
    # - Directly here as resource=Resource.create({"service.name": "dummy_service", "service.namespace": "dummy_repo", "service.version": "xxx", "service.instance.id": "xxx"})
    # - Command params: opentelemetry-instrument --service_name "dummy_service" --resource_attributes "service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" python app.py
    # - Env variables: OTEL_SERVICE_NAME="dummy_service" OTEL_RESOURCE_ATTRIBUTES="service.namespace=dummy_repo,service.version=`echo $GIT_HASH`,service.instance.id=`echo $ECS_TASK_ID`" opentelemetry-instrument python app.py
    # NOTE: Prefer env variables to configure resource here

    if resource is None:
        resource = Resource.create()

    # The tracer sampler can also be configured via environment variables:
    # - OTEL_TRACES_SAMPLER
    #   - always_on - Sampler that always samples spans, regardless of the parent span's sampling decision.
    #   - always_off - Sampler that never samples spans, regardless of the parent span's sampling decision.
    #   - traceidratio - Sampler that samples probabilistically based on rate.
    #   - parentbased_always_on - (DEFAULT) Sampler that respects its parent span's sampling decision, but otherwise always samples.
    #   - parentbased_always_off - Sampler that respects its parent span's sampling decision, but otherwise never samples.
    #   - parentbased_traceidratio - Sampler that respects its parent span's sampling decision, but otherwise samples probabilistically based on rate.
    # - OTEL_TRACES_SAMPLER_ARG
    #   - This is only used for rate based sampling, e.g. traceidratio and parentbased_traceidratio
    #   - Value must be in the range [0.0, 1.0]
    #   - Default is 1.0 (maximum rate) meaning no trace is dropped

    # To configure a rate based sampler, set these environment variables:
    # - OTEL_TRACES_SAMPLER=parentbased_traceidratio
    # - OTEL_TRACES_SAMPLER_ARG=0.01

    sampler = None  # TracerProvider below defaults to sampler="parentbased_always_on" when the provided sampler is None
    if debug:
        sampler = ALWAYS_OFF  # Turn off tracing in debug mode

    # CRITICAL: Do not miss to set the TracerProvider globally!
    # NOTE: set_tracer_provider(...) here is redundant if we run this service
    # via opentelemetry-instrument. This is because opentelemetry-instrument
    # automatically initializes a TracerProvider and sets it globally using
    # set_tracer_provider(...). Since the global tracer provider can only be set
    # once via set_tracer_provider(), and opentelemetry-instrument already sets
    # it, the following call to set_tracer_provider() becomes redundant. Please
    # BEWARE that this means suresdk's TracerProvider is not set globally. So
    # you should use the tracer provider created here to create your traces, and
    # don't rely on get_tracer_provider().get_tracer(...) to get traces as it will
    # use the wrong TracerProvider (the one set by opentelemetry-instrument).
    set_tracer_provider(TracerProvider(sampler=sampler, resource=resource))

    # TODO: Add support for "env=..." label
    tracer = trace.get_tracer(instrumenting_module_name="suresdk")

    _logger.info("OTLP Tracer created successfully")

    return tracer
