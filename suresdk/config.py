from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

OTEL_RESOURCE = Resource.create()


class SureSDKConfig:
    DEBUG = False

    ENV = (
        OTEL_RESOURCE.attributes.get(ResourceAttributes.DEPLOYMENT_ENVIRONMENT)
        or "prod"
    )

    REPO = OTEL_RESOURCE.attributes.get(ResourceAttributes.SERVICE_NAMESPACE) or ""
    SERVICE = OTEL_RESOURCE.attributes.get(ResourceAttributes.SERVICE_NAME) or ""
    SERVICE_VERSION = (
        OTEL_RESOURCE.attributes.get(ResourceAttributes.SERVICE_VERSION) or ""
    )
    SERVICE_INSTANCE_ID = (
        OTEL_RESOURCE.attributes.get(ResourceAttributes.SERVICE_INSTANCE_ID) or ""
    )

    SERVICE_LOG_LEVEL = config_store.get("SERVICE_LOG_LEVEL", "INFO").upper()

    # SSL_CERT_FILE is used to provide path to a custom CA certificate to handle SSL in
    # some libraries, e.g. confluent_kafka, redis
    SSL_CERT_FILE = config_store.get("SSL_CERT_FILE")
