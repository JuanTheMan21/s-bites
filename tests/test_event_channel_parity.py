"""The three ``EventChannel`` implementations, held to one set of assertions.

``fake`` and ``local`` run offline, in-process. ``servicebus`` (T34) is marked ``live`` and
deselected by default -- each test gets its own throwaway topic and subscription
(``tests.azure_live.throwaway_topic_subscription``), for the same isolation reason
``test_job_queue_parity.py``'s ``throwaway_queue`` exists: a shared subscription risks a test
receiving an event a previous, differently-asserting test published.

Every ``queue.get()`` below is wrapped in ``asyncio.wait_for`` -- immediate for ``fake``/
``local``, genuinely asynchronous for ``servicebus`` (publish sends to the topic; the
subscriber's own background pump is what delivers it back), so a bare ``await`` with no timeout
would hang forever on a real regression rather than failing the test.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest

from adapters.azure.event_channel import ServiceBusEventChannel
from adapters.local.event_channel import LocalEventChannel
from interfaces import EventChannel
from tests.azure_live import SERVICE_BUS_CONNECTION_STRING, require, throwaway_topic_subscription
from tests.fakes import FakeEventChannel

IMPLEMENTATIONS = ["fake", "local", pytest.param("servicebus", marks=pytest.mark.live)]
GET_TIMEOUT_S = 15.0


@pytest.fixture(params=IMPLEMENTATIONS)
async def channel(request: pytest.FixtureRequest) -> AsyncIterator[EventChannel]:
    if request.param == "fake":
        yield FakeEventChannel()
        return
    if request.param == "local":
        local = LocalEventChannel()
        await local.start()
        yield local
        return

    async with throwaway_topic_subscription() as (topic, subscription):
        sb_channel = ServiceBusEventChannel(
            require(SERVICE_BUS_CONNECTION_STRING), topic, subscription
        )
        await sb_channel.start()
        try:
            yield sb_channel
        finally:
            await sb_channel.aclose()


async def test_a_subscriber_receives_a_published_event(channel: EventChannel) -> None:
    queue = await channel.subscribe("job-1")

    await channel.publish("job-1", {"stage": "start"})

    # T18M/D197: every delivered event now also carries a server-stamped "at" -- checked
    # separately in test_event_channel_parity.py's own history tests; irrelevant to what this
    # test asserts, so excluded here rather than pinning a real wall-clock value.
    event = await asyncio.wait_for(queue.get(), timeout=GET_TIMEOUT_S)
    assert {k: v for k, v in event.items() if k != "at"} == {"stage": "start"}


async def test_every_current_subscriber_gets_the_same_event(channel: EventChannel) -> None:
    first = await channel.subscribe("job-1")
    second = await channel.subscribe("job-1")

    await channel.publish("job-1", {"stage": "start"})

    first_event = await asyncio.wait_for(first.get(), timeout=GET_TIMEOUT_S)
    second_event = await asyncio.wait_for(second.get(), timeout=GET_TIMEOUT_S)
    assert first_event == second_event
    assert {k: v for k, v in first_event.items() if k != "at"} == {"stage": "start"}


async def test_end_stream_puts_the_sentinel_a_subscriber_stops_on(channel: EventChannel) -> None:
    queue = await channel.subscribe("job-1")

    await channel.end_stream("job-1")

    assert await asyncio.wait_for(queue.get(), timeout=GET_TIMEOUT_S) is None


async def test_unsubscribe_stops_delivery_to_that_queue(channel: EventChannel) -> None:
    queue = await channel.subscribe("job-1")
    await channel.unsubscribe("job-1", queue)

    await channel.publish("job-1", {"stage": "start"})
    # Nothing to await here -- proving absence needs a different shape than proving presence.
    # A short, generous sleep is the honest way to say "and nothing arrived after a real chance
    # to," the same tradeoff every negative-delivery assertion in an async system makes.
    await asyncio.sleep(1.0)
    assert queue.empty()


async def test_publish_with_no_subscribers_is_not_an_error(channel: EventChannel) -> None:
    """The same reasoning as JobQueue.dequeue's empty case: a subscriber connecting after this
    call started is a normal race, not a bug to raise on."""
    await channel.publish("job-with-nobody-watching", {"stage": "start"})


async def test_history_replays_every_published_event_in_order(channel: EventChannel) -> None:
    """T18M/D197: this is what closes the "connects after this call started is a normal race"
    gap ``publish``'s own docstring names -- a subscriber joining late must still be able to see
    what already happened, via ``history``, not lose it."""
    await channel.publish("job-1", {"stage": "outline", "edge": "start"})
    await channel.publish("job-1", {"stage": "voice", "edge": "start"})

    # servicebus delivers via its own background pump, not synchronously with publish() -- give
    # it a real chance to land before asserting, the same tolerance GET_TIMEOUT_S already grants
    # every other assertion in this file for that implementation specifically.
    for _ in range(50):
        if len(await channel.history("job-1")) >= 2:
            break
        await asyncio.sleep(GET_TIMEOUT_S / 50)

    history = await channel.history("job-1")
    # Every event is stamped with a server-side "at" (T18M/D197) -- checked separately below
    # since its exact value is real wall-clock time, not something to pin in this assertion.
    assert [{k: v for k, v in event.items() if k != "at"} for event in history] == [
        {"stage": "outline", "edge": "start"},
        {"stage": "voice", "edge": "start"},
    ]
    assert all(isinstance(event["at"], int) for event in history)


async def test_history_of_an_unpublished_job_is_empty(channel: EventChannel) -> None:
    assert await channel.history("nobody-ever-published-to-this-job") == []


async def test_an_event_already_carrying_at_is_never_overwritten(channel: EventChannel) -> None:
    """T18M/D197: the one case ``publish`` must NOT stamp -- a message already carrying its true
    origin time (a ``ServiceBusEventChannel`` pump re-publishing one it received over the wire,
    which was already stamped by the ORIGINAL sender's own ``publish`` call)."""
    await channel.publish("job-1", {"stage": "outline", "edge": "start", "at": 42})

    for _ in range(50):
        if await channel.history("job-1"):
            break
        await asyncio.sleep(GET_TIMEOUT_S / 50)

    history = await channel.history("job-1")
    assert history[0]["at"] == 42
