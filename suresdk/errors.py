class ValidationError(Exception):
    # This error indicates that the data is invalid. This error MUST only be
    # used when there is no way to resolve the situation on its own. Such
    # situations should be brought to the user's notice ASAP, so they can
    # intervene and fix the data themselves.
    pass


class ResourceNotFound(Exception):
    # Also known as 404.
    # This error indicates that a resource/entity could not be found and there
    # is no way to resolve the situation on its own. Such situations should be
    # brought to the user's notice ASAP, so they can intervene and fix the data
    # themselves.
    pass


class RetriableError(Exception):
    # This error indicates that the error is not fatal immediately, and should get
    # resolved if processing is retried. This error should only be thrown if it is
    # caused by bad luck.
    # e.g. When we enter into deadlock with another process, then we can raise this
    # error, and retry the processing. If we are lucky, we won't enter into a deadlock
    # again.
    pass


class RetriableRepeatableReadError(RetriableError):
    # This error indicates the error was caused because somehow the assumption of
    # processing the data in a simluated/real Repeatable Read isolation got violated.
    # This is not fatal immediately, and should get resolved with subsequent retries.
    pass


class RetriableDatabaseRepeatableReadError(RetriableRepeatableReadError):
    # This error indicates the error was caused because the Database (e.g. MySQL,
    # PostgreSQL, Solr, Opensearch, etc.) refused to save our data because it violated
    # Repeatable Read isolation level. This is not fatal immediately, and should get
    # resolved with subsequent retries.
    pass
