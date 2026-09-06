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

    event = await asyncio.wait_for(queue.get(), timeout=GET_TIMEOUT_S)
    assert event == {"stage": "start"}


async def test_every_current_subscriber_gets_the_same_event(channel: EventChannel) -> None:
    first = await channel.subscribe("job-1")
    second = await channel.subscribe("job-1")

    await channel.publish("job-1", {"stage": "start"})

    assert await asyncio.wait_for(first.get(), timeout=GET_TIMEOUT_S) == {"stage": "start"}
    assert await asyncio.wait_for(second.get(), timeout=GET_TIMEOUT_S) == {"stage": "start"}


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
