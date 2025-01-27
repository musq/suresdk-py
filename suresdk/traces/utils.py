from contextlib import contextmanager
from typing import Callable

from opentelemetry import trace

TRACER = trace.get_tracer(instrumenting_module_name="suresdk")


def trace_function(span_name: str | None = None) -> Callable:
    """
    Decorator to trace a function.
    Uses the decorated function name as span name, by default.

    Usage:
    - Provide a custom span name:
      @trace_function(span_name="custom_span")
    - Use the function name as the span name:
      @trace_function()
    """
    from functools import wraps

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def new_func(*args, **kwargs):
            with TRACER.start_as_current_span(name=span_name or fn.__name__):
                return fn(*args, **kwargs)

        return new_func

    return decorator


@contextmanager
def trace_snippet(span_name: str):
    """
    Context Manager to trace a snippet.

    Usage: with trace_snippet(span_name="custom_span"): ...
    """

    with TRACER.start_as_current_span(name=span_name):
        yield
