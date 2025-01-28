import functools
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import redis_lock

from .config import SureSDKConfig
from .traces import trace_snippet
from .utils import serialize


def ttl_cache(
    name: str | None = None,
    ttl: int | None = None,
    maxsize: int | None = None,
):
    """
    Features:
    - This decorator sits on top of the expensive calculation function, so the interface
      is clean.
    - You can specify a custom cache key name. Otherwise it'll use the function name as
      cache key as fallback. Cache key will be namespaced by SERVICE name.
    - You can specify an optional TTL too
    - You can specify an optional maxsize too
    - You can also pass an optional argument __clear_cache = True during runtime, to
      forcefully delete any cached value, then run the expensive function and re-cache
      the result.

    Usage:
    # Decorate desired function
    expensive_calculation = ttl_cache(ttl=10)(expensive_calculation)

    result1 = expensive_calculation(3, 4)  # This will be slow because the cache is empty
    result2 = expensive_calculation(3, 4)  # This should be fast (cached for 10 seconds)

    # Force clear the cache for the expensive_calculation function.
    # This will be slow because first the cache is cleared, then it is repopulated after
    # the expensive calculation is done.
    result3 = expensive_calculation(3, 4, __clear_cache=True)

    # This should be fast because the cache has already been set in the previous step.
    result4 = expensive_calculation(3, 4)
    """

    def decorator(func: Callable):
        local_cache_key_vs_last_updated_on: dict[str, float] = {}
        local_cache_key_vs_data: OrderedDict[str, Any] = OrderedDict()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a cache key based on the service name, function name and the
            # function arguments. Make sure to remove the __clear_cache from keyword
            # args so it doesn't pollute the cache key.
            kwargs_copy = deepcopy(kwargs)
            kwargs_copy.pop("__clear_cache", None)
            key = f"{SureSDKConfig.SERVICE}:{name or func.__name__}:{serialize(args)}:{serialize(kwargs_copy)}"
            cache_key = f"cache:{key}"

            # Check if a special argument '__clear_cache' is provided. Here we do not
            # pop the '__clear_cache' param to continue propagating to other downstream
            # decorators.
            clear_cache = kwargs.get("__clear_cache", False)
            if clear_cache:
                # Remove the cache_key from local cache to behave as no caching
                local_cache_key_vs_last_updated_on.pop(cache_key, None)
                local_cache_key_vs_data.pop(cache_key, None)

            local_last_updated_on = local_cache_key_vs_last_updated_on.get(cache_key)

            if local_last_updated_on is None:
                # At this point local cache has not been bootstrapped, so we bootstrap
                # it by fetching data from original source
                local_cache_key_vs_data[cache_key] = func(*args, **kwargs)
                local_cache_key_vs_last_updated_on[cache_key] = time.time()

                if maxsize is not None:
                    # Make sure the size of cache doesn't exceed
                    while len(local_cache_key_vs_data) > maxsize:
                        ejected_key, ejected_item = local_cache_key_vs_data.popitem(
                            last=False
                        )
                        local_cache_key_vs_last_updated_on.pop(ejected_key, None)

                return local_cache_key_vs_data[cache_key]

            # Move the current key-value to end to indicate LRU pattern
            local_cache_key_vs_data.move_to_end(cache_key)

            if ttl is None:
                # Local cache can never be stale
                return local_cache_key_vs_data[cache_key]
            else:
                if local_last_updated_on >= (time.time() - ttl):
                    # Local cache is not stale yet!
                    return local_cache_key_vs_data[cache_key]
                else:
                    # At this point the local_last_updated_on is outdated, so the local data is
                    # stale. So we call the original function to get the data again.
                    local_cache_key_vs_data[cache_key] = func(*args, **kwargs)
                    local_cache_key_vs_last_updated_on[cache_key] = time.time()

                    if maxsize is not None:
                        # Make sure the size of cache doesn't exceed
                        while len(local_cache_key_vs_data) > maxsize:
                            ejected_key, ejected_item = local_cache_key_vs_data.popitem(
                                last=False
                            )
                            local_cache_key_vs_last_updated_on.pop(ejected_key, None)

                    return local_cache_key_vs_data[cache_key]

        return wrapper

    return decorator


def redis_cache(
    redis_client,  # TODO: Add type hint for redis_client: redis.Redis
    name: str | None = None,
    ttl: int | None = None,
    serializer: Callable[[Any], str | bytes] = json.dumps,
    deserializer: Callable[[str | bytes], Any] = json.loads,
):
    """
    Features:
    - This decorator sits on top of the expensive calculation function, so the interface
      is clean.
    - You can specify a custom cache key name. Otherwise it'll use the function name as
      cache key as fallback. Cache key will be namespaced by SERVICE name.
    - You can specify an optional TTL too
    - You can also pass an optional argument __clear_cache = True during runtime, to
      forcefully delete any cached value, then run the expensive function and re-cache
      the result.
    - This decorator takes care of thundering herd calls.
      - So if there are multiple workers running on parallel, and the cache expires,
        then not all of them will call the expensive function. The expensive function
        will be called only once.
      - How it works: One of the workers will acquire a redis lock, then run the
        expensive function and cache it, then release the lock. During lock, other
        workers are blocked from accessing the cache. But as soon as the lock is
        released, all the other workers will try again to fetch the cache, and they will
        find it (because the 1st worker already set it). So they won't need to run the
        expensive calculation again.

    Usage:
    RECOMMENDED: Create a partial function by providing the Redis Client. This will
    make redis_cache decorator easier to use as we won't need to provide the redis
    client again and again.
    ```
    import functools
    import redis
    from suresdk import cache

    REDIS_CLIENT = redis.Redis(...)
    redis_cache = functools.partial(cache.redis_cache, redis_client=REDIS_CLIENT)
    ```

    # Decorate desired function
    expensive_calculation = redis_cache(ttl=10)(expensive_calculation)

    result1 = expensive_calculation(3, 4)  # This will be slow because the cache is empty
    result2 = expensive_calculation(3, 4)  # This should be fast (cached for 10 seconds)

    # Force clear the cache for the expensive_calculation function.
    # This will be slow because first the cache is cleared, then it is repopulated after
    # the expensive calculation is done.
    result3 = expensive_calculation(3, 4, __clear_cache=True)

    # This should be fast because the cache has already been set in the previous step.
    result4 = expensive_calculation(3, 4)
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a cache key based on the service name, function name and the
            # function arguments. Make sure to remove the __clear_cache from keyword
            # args so it doesn't pollute the cache key.
            kwargs_copy = deepcopy(kwargs)
            kwargs_copy.pop("__clear_cache", None)
            key = f"{SureSDKConfig.SERVICE}:{name or func.__name__}:{serialize(args)}:{serialize(kwargs_copy)}"
            cache_key = f"cache:{key}"

            # Check if a special argument '__clear_cache' is provided
            clear_cache = kwargs.get("__clear_cache", False)

            if clear_cache:
                # If the clear cache flag is set, delete the cached result
                redis_client.delete(cache_key)

            # Try to fetch the result from cache
            cached_result = redis_client.get(cache_key)
            if cached_result is not None:
                # If the result is in cache, return it immediately
                result = deserializer(cached_result)
                return result

            with trace_snippet(span_name=f"redis_cache:{func.__name__}"):
                # Avoid thundering herd using this reference:
                # https://github.com/ionelmc/python-redis-lock/blob/master/src/redis_lock/django_cache.py#L21
                lock = redis_lock.Lock(
                    redis_client=redis_client,
                    name=key,
                    expire=300,  # Assume it could take at most 5m to execute the expensive call!
                    strict=False,  # This does nothing, but is required by the redis_lock library!
                )

                block_timeout = 300  # in seconds
                if not lock.acquire(blocking=True, timeout=block_timeout):
                    raise redis_lock.NotAcquired(
                        f"Redis lock could not be acquired within {block_timeout}s - {lock._name}"
                    )

                try:
                    # Try to fetch the result from cache again. Hopefully this time the
                    # value has been set by the process that held the lock just prior to
                    # this process.
                    cached_result = redis_client.get(cache_key)
                    if cached_result is not None:
                        # If the result is in cache, return it
                        result = deserializer(cached_result)
                    else:
                        # If the result is not in cache, compute it and store in cache
                        result = func(*args, **kwargs)

                        if ttl is not None:
                            redis_client.setex(cache_key, ttl, serializer(result))
                        else:
                            redis_client.set(cache_key, serializer(result))
                except Exception:
                    raise
                finally:
                    # Critical step: Release the lock!
                    lock.release()

            return result

        return wrapper

    return decorator
