from collections.abc import Callable

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)

from ..errors import RetriableRepeatableReadError


def execute_with_retries(callback: Callable, max_attempts: int = 5, **callback_kwargs):
    for attempt in Retrying(
        retry=retry_if_exception_type(RetriableRepeatableReadError),
        stop=stop_after_attempt(max_attempts),
        wait=wait_incrementing(start=1, increment=1, max=5),
    ):
        with attempt:
            return callback(**callback_kwargs)
