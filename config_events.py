"""``EventChannel`` resolution, split out of ``config.py`` the same way ``config_queue.py`` and
``config_render.py`` already are -- one new interface's growth (a third stub-until/bridge seam)
staying in its own file rather than crowding the module every other interface's resolution lives
in.

Still config-seam code, not adapter logic: it names the two concrete classes ``config.py``
already imports (``LocalEventChannel``, ``ServiceBusEventChannel``) and nothing else does.
"""

from collections.abc import Mapping

from adapters.azure.event_channel import ServiceBusEventChannel
from adapters.local.event_channel import LocalEventChannel
from interfaces import EventChannel


def events_env(env: Mapping[str, str]) -> str:
    """``EVENTS_ENV`` is the same bridge shape ``config_render.py::render_env`` and
    ``config_queue.py::queue_env`` already are. Unlike those two, ``ServiceBusEventChannel`` is
    real from the moment it lands (T34), not a stub waiting on a later task -- this bridge exists
    for the same reason those do regardless: it lets ``RUNTIME_ENV=azure`` pair with a fully
    in-process progress channel while iterating locally, without hand-mixing adapters outside of
    labeled code. Defaults to ``RUNTIME_ENV`` when unset.

    **One real, permanent constraint hides behind this bridge, not a temporary one:**
    ``ServiceBusEventChannel`` manages exactly one fixed subscription
    (``AZURE_SERVICE_BUS_SUBSCRIPTION``), which is only correct while the API itself runs at a
    single replica -- see the class's own docstring. Lifting that later needs a subscription per
    replica, which is new code, not a config change; this bridge does not cover that gap.
    """
    value = env.get("EVENTS_ENV", "").strip()
    return value or env.get("RUNTIME_ENV", "")


def resolve(env: Mapping[str, str]) -> EventChannel:
    """Resolve the event channel against ``events_env(env)``, not ``RUNTIME_ENV`` directly."""
    if events_env(env) == "local":
        return LocalEventChannel()
    return ServiceBusEventChannel(
        env.get("AZURE_SERVICE_BUS_CONNECTION_STRING", ""),
        env.get("AZURE_SERVICE_BUS_TOPIC", "").strip() or "job-events",
        env.get("AZURE_SERVICE_BUS_SUBSCRIPTION", "").strip() or "api",
    )
