import fnmatch
import logging
import os
from abc import ABC
from collections.abc import Callable
from operator import attrgetter
from signal import SIGINT, SIGTERM, signal, strsignal
from typing import Any, Self

from common.utils import Config
from common.utils.apm import profile_function, profile_snippet
from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    TopicPartition,
)
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)

from ..errors import RetriableRepeatableReadError
from ..utils import csv_to_list, group_by

_logger = logging.getLogger(__name__)


def execute_with_retries(callback: Callable, max_attempts: int = 5, **callback_kwargs):
    for attempt in Retrying(
        retry=retry_if_exception_type(RetriableRepeatableReadError),
        stop=stop_after_attempt(max_attempts),
        wait=wait_incrementing(start=1, increment=1, max=5),
    ):
        with attempt:
            return callback(**callback_kwargs)


def message_belongs_to_current_consumer(
    current_consumer: str | None, target_consumers: str | None
) -> bool:
    """
    If current_consumer = "abc"

    Supported target_consumers which match "abc":
    None
    ""
    "*"
    "ab*"
    "*b*"
    "*bc"
    "abc,xyz"
    "ab*,xy*"
    "*yz,*bc"
    "xy*,*"
    "-xy*"
    "*,-xy*"
    "-xy*,-pq*"

    Supported target_consumers which don't match "abc":
    "xyz"
    "xy*"
    "*yz"
    "*y*"
    "x*,pqr"
    "*,-abc"
    "-ab*,*"
    "-*b*"
    "-*,*"
    "-*"
    "--*"
    "-"
    "--"
    """

    if (current_consumer is None) or (current_consumer == ""):
        return True

    if (target_consumers is None) or (target_consumers == ""):
        return True

    target_consumer_patterns = csv_to_list(str(target_consumers))

    # Remove leading "-" from all negative patterns
    negative_patterns = [
        pattern.lstrip("-")
        for pattern in target_consumer_patterns
        if pattern.startswith("-")
    ]
    negative_patterns = [np if np else "*" for np in negative_patterns]

    positive_patterns = [
        pattern for pattern in target_consumer_patterns if not pattern.startswith("-")
    ]

    for pattern in negative_patterns:
        # If any negative pattern matches the current_consumer, then it is considered a
        # negative match!
        if fnmatch.fnmatch(current_consumer, pattern):
            return False

    # If all patterns are negative and none of them match the current_consumer, then it
    # is considered a positive match!
    if negative_patterns and not positive_patterns:
        return True

    for pattern in positive_patterns:
        # At this point, no negative patterns match the current_consumer, and positive
        # patterns are also present. So if any positive pattern matches the
        # current_consumer, then it is considered a positive match!
        if fnmatch.fnmatch(current_consumer, pattern):
            return True

    return False


class KafkaProcessor(ABC):
    def __init__(
        self,
        kafka_topics: list[str],
        kafka_consumer_config: dict[str, Any],
        batch_size: int,
        parse_and_validate_message: Callable[[Message], tuple[bool, Any]],
        hydrate_repeatable_read_caches: Callable[[list], None],
        check_event_relevance: Callable[[Any], bool],
        process_one_batch_of_events: Callable,
    ):
        self.interrupted = False
        self.kafka_topics = list(set(kafka_topics))
        self.kafka_consumer_config = kafka_consumer_config
        self.batch_size = batch_size
        self.parse_and_validate_message = parse_and_validate_message
        self.hydrate_repeatable_read_caches = hydrate_repeatable_read_caches
        self.check_event_relevance = check_event_relevance
        self.process_one_batch_of_events = process_one_batch_of_events

        # TODO: I don't know why librdkafka isn't able to use SSL_CERT_FILE OpenSSL
        # environment variable by default i.e. without assistance as follows. This env
        # var works fine with dpkp/kafka-python library.
        # https://github.com/confluentinc/confluent-kafka-python/issues/527#issuecomment-512773232
        if SSL_CERT_FILE := os.environ.get("SSL_CERT_FILE"):
            self.kafka_consumer_config["ssl.ca.location"] = SSL_CERT_FILE

    def __enter__(self) -> Self:
        self.original_sigint_handler = signal(SIGINT, self.handle_interrupt)
        self.original_sigterm_handler = signal(SIGTERM, self.handle_interrupt)

        self.kafka_consumer = Consumer(self.kafka_consumer_config)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.kafka_consumer.close()  # This operation may block

        signal(SIGTERM, self.original_sigterm_handler)
        signal(SIGINT, self.original_sigint_handler)

    def handle_interrupt(self, signalnum, stack_frame):
        """
        We set the interrupted flag to True, so that our process exits gracefully after
        finishing the current task.
        """
        self.interrupted = True
        _logger.warning(
            f"Interrupt received <signal={strsignal(signalnum)}:{signalnum}>, will exit after processing current loop"
        )

    def on_revoke(self, consumer: Consumer, topic_partitions: list[TopicPartition]):
        topic_vs_partitions = {
            topic: sorted([tp.partition for tp in tps])
            for topic, tps in group_by(
                topic_partitions, key=attrgetter("topic")
            ).items()
        }
        if topic_vs_partitions:
            _logger.warning(
                "Revoked partitions",
                extra={"body": {"topic_vs_partitions": topic_vs_partitions}},
            )

    def on_assign(self, consumer: Consumer, topic_partitions: list[TopicPartition]):
        topic_vs_partitions = {
            topic: sorted([tp.partition for tp in tps])
            for topic, tps in group_by(
                topic_partitions, key=attrgetter("topic")
            ).items()
        }
        if topic_vs_partitions:
            _logger.warning(
                "Assigned partitions",
                extra={"body": {"topic_vs_partitions": topic_vs_partitions}},
            )

    @profile_function(
        operation="workers", resource=f"{Config.SERVICE} :: process_messages"
    )
    def process_messages(self, messages) -> list[TopicPartition]:
        tp_vs_offset_to_commit = {}
        events = []

        with profile_snippet(resource="parse_and_validate_messages"):
            # Collect only valid messages for processing
            for msg in messages:
                if msg is None:
                    # Message is empty
                    continue

                elif msg is not None and msg.error() is not None:
                    # Error carrying message
                    continue

                elif msg is not None and msg.error() is None:
                    # Payload carrying message

                    tp_vs_offset_to_commit[(msg.topic(), msg.partition())] = (
                        msg.offset() + 1
                    )

                    message_is_valid, event = self.parse_and_validate_message(msg)
                    if not message_is_valid:
                        continue

                    events.append(event)

        events_to_process = []
        if events:
            with profile_snippet(resource="hydrate_repeatable_read_caches"):
                self.hydrate_repeatable_read_caches(events)

            with profile_snippet(resource="check_events_relevance"):
                for event in events:
                    event_is_relevant = self.check_event_relevance(event)
                    if event_is_relevant:
                        events_to_process.append(event)

        if events_to_process:
            with profile_snippet(resource="process_one_batch_of_events"):
                self.process_one_batch_of_events(events_to_process)

        offsets_to_commit = [
            TopicPartition(topic=tp_tuple[0], partition=tp_tuple[1], offset=offset)
            for tp_tuple, offset in tp_vs_offset_to_commit.items()
        ]

        return offsets_to_commit

    def run_forever(self):
        _logger.info(
            "Listening for messages in Kafka",
            extra={"body": {"topics": self.kafka_topics}},
        )
        self.kafka_consumer.subscribe(
            self.kafka_topics,
            on_assign=self.on_assign,
            on_revoke=self.on_revoke,
        )

        while not self.interrupted:
            """
            NOTE: It is recommeded to shut down any running task within 30s of
            receiving an interrupt. After 30s, the task is going to get forcefully
            shut down by AWS. So, make sure P99 of each loop here is < 30s.
            """
            messages = self.kafka_consumer.consume(
                num_messages=self.batch_size, timeout=3
            )

            messages = [msg for msg in messages if msg is not None]

            offsets_to_commit = []
            if messages:
                offsets_to_commit = execute_with_retries(
                    self.process_messages, messages=messages
                )

            # Now try to commit the offsets. We are simulating Repeatable Read isolation
            # level in Kafka here. The assumption here is that if there has been a
            # change in Kafka by the time we are trying to commit offsets (e.g.
            # rebalancing, etc.), then committing the offset would result in an error.
            # If the error is retriable, then we can simply go around the loop.
            # Otherwise, if the error is non-retriable, then there is no way to handle
            # it, and we raise the exception. As a result, the current worker will die.
            try:
                if offsets_to_commit:
                    self.kafka_consumer.commit(
                        offsets=offsets_to_commit, asynchronous=False
                    )
            except KafkaException as ke:
                match ke.args[0].code():
                    case KafkaError.UNKNOWN_MEMBER_ID:
                        # This occurs when a consumer gets kicked out by the Broker
                        # because it expired. e.g. when this consumer exceeded
                        # max.poll.timeout.ms during processing. This is fine, because
                        # we'll immediately do another poll() and we'll again become
                        # part of the Consumer Group. The only catch is, the events that
                        # could not be committed in this loop will be processed again.
                        # So, ensure idempotency when processing events!
                        pass
                    case KafkaError.ILLEGAL_GENERATION:
                        # This occurs when a consumer's metadata is stale and it tries
                        # to commit offset with an older Generation ID. Kafka Broker
                        # detects this and issues this error. We can simply ignore this
                        # error and proceed to poll without committing. This will update
                        # this consumer's metadata. The only catch is, the events that
                        # could not be committed in this loop will be processed again.
                        # So, ensure idempotency when processing events!
                        pass
                    case KafkaError.REBALANCE_IN_PROGRESS:
                        # This occurs when the broker is rebalancing partitions in a
                        # consumer group, and one of the consumers tries to commit
                        # offset during this interval. This is considered an invalid and
                        # expired operation. However ignoring this error is fine,
                        # because we'll immediately do another poll() next, and we'll
                        # get assigned new partitions and their events, and our loop
                        # will continue as usual. The only catch is, the events that
                        # could not be committed in this loop will be processed again.
                        # So, ensure idempotency when processing events!
                        pass
                    case _:
                        raise
