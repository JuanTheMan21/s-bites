"""``EventChannel`` backed by a Service Bus topic (T34).

**Why a topic, not a queue.** A queue hands each message to exactly one receiver; this channel's
whole job is fanning one job's events out to whatever SSE connections happen to be open on
whichever API replica they landed on. A topic with one subscription per replica is the shape that
matches -- this adapter currently manages exactly one subscription, because the API runs at one
replica (see ``config_events.py``'s docstring for what changes if that ever lifts).

Publishing and subscribing are two different concerns wearing one adapter: ``publish``/
``end_stream`` send to the topic; ``subscribe``/``unsubscribe`` are answered by a private
``LocalEventChannel`` that ``start()``'s background pump feeds from the subscription -- so the
part of this class the SSE endpoint actually touches is identical in shape to the fully local
adapter, and only the plumbing behind it differs.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus.exceptions import ServiceBusError

from adapters.azure.servicebus_errors import translate
from adapters.local.event_channel import LocalEventChannel
from interfaces import EventChannel, check_event_serialisable

logger = logging.getLogger(__name__)

# Capped exponential backoff for _pump's reconnect loop -- see its own docstring for why this
# exists at all.
PUMP_INITIAL_BACKOFF_S = 1.0
PUMP_MAX_BACKOFF_S = 60.0


class ServiceBusEventChannel(EventChannel):
    def __init__(self, connection_string: str, topic_name: str, subscription_name: str) -> None:
        self.connection_string = connection_string
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self._client = ServiceBusClient.from_connection_string(connection_string)
        self._sender = self._client.get_topic_sender(topic_name)
        self._receiver = self._client.get_subscription_receiver(topic_name, subscription_name)
        self._local = LocalEventChannel()
        self._pump_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Begin the background pump that replays the subscription into the local fan-out.
        Idempotent -- a second call while a pump is already running is a no-op, since restarting
        it would double-consume the subscription."""
        if self._pump_task is not None:
            return
        self._pump_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        """Retries forever, with capped exponential backoff, rather than exiting.

        **Found by review, not assumed correct in advance:** the first version's outer
        ``try/except`` caught a connection-level failure (a dropped AMQP link, a transient
        Service Bus blip -- exactly what ``ServiceBusError`` exists to name), logged it once, and
        let the coroutine return. ``self._pump_task`` was then a *finished* task, not ``None``, so
        ``start()``'s own idempotency guard permanently no-opped on every future call -- nothing
        ever revived it. One transient network hiccup would silently and permanently stop live
        progress for every job on this API replica from that moment on, discoverable only by
        reading logs, which is precisely the "hung pipeline with no error anywhere to find"
        failure this whole adapter exists to prevent (see the module docstring). Retrying here,
        for the life of the process, is what keeps that failure transient instead of permanent.
        """
        backoff_s = PUMP_INITIAL_BACKOFF_S
        while True:
            try:
                async for message in self._receiver:
                    try:
                        body = (
                            message.body
                            if isinstance(message.body, bytes | str)
                            else b"".join(message.body)
                        )
                        envelope = json.loads(body)
                        job_id, event = envelope["job_id"], envelope["event"]
                        if event is None:
                            await self._local.end_stream(job_id)
                        else:
                            await self._local.publish(job_id, event)
                        await self._receiver.complete_message(message)
                    except Exception:
                        logger.exception(
                            "event channel pump: dropping one malformed/failed message"
                        )
                backoff_s = PUMP_INITIAL_BACKOFF_S  # a clean iteration end resets the backoff
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "event channel pump lost its connection -- retrying in %.0fs", backoff_s
                )
                await asyncio.sleep(backoff_s)
                backoff_s = min(backoff_s * 2, PUMP_MAX_BACKOFF_S)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        return await self._local.subscribe(job_id)

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        await self._local.unsubscribe(job_id, queue)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        check_event_serialisable(event)
        await self._send(job_id, event)

    async def end_stream(self, job_id: str) -> None:
        await self._send(job_id, None)

    async def _send(self, job_id: str, event: dict[str, Any] | None) -> None:
        body = json.dumps({"job_id": job_id, "event": event})
        try:
            await self._sender.send_messages(ServiceBusMessage(body))
        except ServiceBusError as exc:
            raise translate(exc) from exc

    async def aclose(self) -> None:
        """Off-contract, per D55 -- ``config.close_adapters`` picks this up generically."""
        if self._pump_task is not None:
            self._pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pump_task
        await self._receiver.close()
        await self._sender.close()
        await self._client.close()
