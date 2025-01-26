from collections.abc import Callable
from threading import Lock


class LazyProxy:
    """
    A proxy helper to lazy load resources.

    BEWARE: You are (kinda) entering Metaprogramming Territory!!

    DO NOT MODIFY this class, unless you are sure how Python handles attribute access,
    because modifying attribute access has a number of gotchas. If you still want to
    edit/modify the implementation of this ProxyObject, then I would HIGHLY RECOMMEND
    you go through the following chapter from the book "Fluent Python" BEFOREHAND:
    - Chapter 19: Dynamic Attributes and Properties

    >>> # Example
    >>>
    >>> import logging
    >>>
    >>> def get_logger(name: str) -> logging.Logger:
    >>>     print("Initializing logger...")
    >>>     return logging.getLogger(name=name)
    >>>
    >>> LOG = LazyProxy(get_logger, name="suresdk")
    >>>
    >>> # Note that the logger object hasn't been initialized yet because we haven't
    >>> # used it yet. It will only get initialized once we try to use it. So we don't
    >>> # see the line "Initializing logger..." printed on the terminal yet.
    >>>
    >>> LOG.warning(
    >>>     "Trying to log automatically loads the logger, so you'll be able to see this log"
    >>> )
    >>>
    >>> # We also see the line "Initializing logger..." printed in terminal just before
    >>> # the log. This indicates that the get_logger() function was executed right
    >>> # before it's underlying resource (in this case, the logger object) was accessed.
    """

    def __init__(self, callback: Callable, **callback_kwargs):
        self.callback = callback
        self.callback_kwargs = callback_kwargs
        self.resource = None
        self.callback_execution_count = 0
        self.lock = Lock()

    def __repr__(self):
        return (
            f"LazyProxy({self.callback.__name__}, "
            + ", ".join(
                [f"{key}={value}" for key, value in self.callback_kwargs.items()]
            )
            + ")"
        )

    def __getattr__(self, attr: str):
        if self.resource is None:
            self.initialize_underlying_resource()

        try:
            return getattr(self.resource, attr)
        except AttributeError as e:
            raise AttributeError(
                "Has the proxied resource been initialized yet?"
            ) from e

    def __setattr__(self, attr: str, value):
        if attr in [
            "callback",
            "callback_kwargs",
            "resource",
            "callback_execution_count",
            "lock",
        ]:
            # If the attribute being set is any of the above (e.g. in the
            # __init__() method above), we directly set it on the object,
            # otherwise it creates RecursionError
            object.__setattr__(self, attr, value)
        else:
            if self.resource is None:
                self.initialize_underlying_resource()

            try:
                return setattr(self.resource, attr, value)
            except AttributeError as e:
                raise AttributeError(
                    "Has the proxied resource been initialized yet?"
                ) from e

    def initialize_underlying_resource(self):
        with self.lock:
            # Acquire a lock to ensure single-writer and avoid the situation of
            # multiple threads trying to initialize the underlying resource
            # concurrently.

            if self.resource is not None:
                # Just after acquiring lock, if the current thread sees that
                # the underlying resource was already initialized by another
                # concurrent thread, then the current thread proceeds to use
                # the already initialized resource to avoid executing expensive
                # re-initialization.
                return

            if self.callback_execution_count >= 3:
                raise RuntimeError(
                    f"{self!r} could not initialize the underlying resource even after 3 tries"
                )

            try:
                self.resource = self.callback(**self.callback_kwargs)
            except Exception as e:
                raise RuntimeError(
                    f"{self!r} encountered error when trying to initialize the underlying resource"
                ) from e
            self.callback_execution_count += 1

            if self.resource is None:
                raise ValueError(
                    f"{self!r} returned None upon initialization. This is not allowed"
                    " because the underlying resource of a LazyProxy cannot be None!"
                )
