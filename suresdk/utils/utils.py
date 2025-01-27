import hashlib
import itertools
import random
import threading
import timeit
import traceback
import uuid
import zlib
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone
from typing import Any


def random_id(length: int = 6) -> str:
    """
    This function should be used to generate unique ids for low cardinality
    resources e.g. a B2B customer id.

    BEWARE: In future, this function can be modified to increase the length, or
    add alphanumeric characters to the output. So never rely on the structure
    of the output string. There is no guarantee about the structure of the
    output, other than the fact that the output is always going to be a string.
    """

    # Remove ambigiuous numbers like 0, 1, 5, 8, because they look visually
    # similar to O, l, S, B respectively
    allowed_chars = ["2", "3", "4", "6", "7", "9"]

    return "".join(random.choice(allowed_chars) for _ in range(length))


def uuid1_str() -> str:
    return str(uuid.uuid1())


def uuid4_str() -> str:
    return str(uuid.uuid4())


def group_by(lizt: list[Any], key: Callable[[Any], Any]) -> dict[Any, list[Any]]:
    sorted_list = sorted(lizt, key=key)
    return {k: list(v) for k, v in itertools.groupby(sorted_list, key)}


def id_map(lizt: list[Any], key: Callable[[Any], Any]) -> dict[Any, Any]:
    list_map = group_by(lizt, key=key)
    assert all(len(v) == 1 for v in list_map.values())
    return {k: v[0] for k, v in list_map.items()}


def generate_traceback_from_exception_details(exc_type, exc_value, tb) -> str:
    return "".join(traceback.format_exception(exc_type, exc_value, tb))


def generate_traceback(exception: Exception) -> str:
    return generate_traceback_from_exception_details(
        type(exception), exception, exception.__traceback__
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_ms() -> int:
    return second_to_ms(utc_now().timestamp())


def second_to_ms(second: float) -> int:
    return round(1000 * second)


def ms_to_second(ms: int) -> float:
    return ms / 1000


def csv_to_list(csv: str) -> list[str]:
    """Convert a comma separated string to a list."""
    return [item.strip() for item in csv.split(",") if item.strip()]


def list_to_csv(lizt: list[str], space: bool = False) -> str:
    """Convert a list to comma separated string."""
    delimiter = ", " if space else ","
    return delimiter.join([item.strip() for item in lizt if item.strip()])


def csv_to_set(csv: str) -> set[str]:
    """Convert a comma separated string to a set."""
    return set(csv_to_list(csv))


def set_to_csv(cet: set[str], space: bool = False) -> str:
    """Convert a set to sorted comma separated string."""
    return list_to_csv(sorted(cet), space=space)


def lines_to_list(lines: str, delimiter: str = "\n") -> list[str]:
    """Convert lines to a list. Make each line an item of the list."""
    return [item.strip() for item in lines.split(delimiter) if item.strip()]


def list_to_lines(lizt: list[str], delimiter: str = "\n") -> str:
    """Convert a list to lines. Keep each item in the list in a new line."""
    return delimiter.join([item.strip() for item in lizt if item.strip()])


def crc32(text) -> str:
    crc = zlib.crc32(str(text).encode("utf-8"))
    return "{:08x}".format(crc & 0xFFFFFFFF)


def sha256(text) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def chunked(it: Iterable, size: int) -> Iterator[list]:
    """Break up large list of data into smaller chunks."""
    assert size > 0, "Input size must be > 0"

    chunk = []
    for item in it:
        chunk.append(item)

        if len(chunk) >= size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk


def current_thread_id() -> str:
    current_thread = threading.current_thread()
    thread_id = current_thread.ident
    return str(thread_id)


class Timer:
    """
    A context manager to measure time taken by a code block.
    e.g.
    >>> with Timer() as timer:
            execute_dummy_task()

    >>> print(timer.elapsed)
    """

    def __init__(self):
        self.elapsed = 0.0

    def __enter__(self) -> "Timer":
        self.start = timeit.default_timer()
        return self

    def __exit__(self, type, value, traceback):
        self.end = timeit.default_timer()
        self.elapsed = self.end - self.start
