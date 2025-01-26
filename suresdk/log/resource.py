from opentelemetry.sdk.resources import Resource, get_aggregated_resources

OTEL_RESOURCE = get_aggregated_resources(
    initial_resource=Resource.create(
        # https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-semantic-conventions/src/opentelemetry/semconv/_incubating/attributes/service_attributes.py
        {
            "service.namespace": "team-3",
            "service.name": "shoppingcart",
            "service.instance.id": "instance-12",
            "service.version": "githash",
        }
    ),
    # Enable additional resource detectors if you need them
    # https://opentelemetry-python.readthedocs.io/en/latest/sdk/resources.html#opentelemetry.sdk.resources.ResourceDetector
    detectors=[
        # OTELResourceDetector(),
        # ProcessResourceDetector(),
        # OsResourceDetector(),
        # _HostResourceDetector(),
    ],
)
