"""Request bodies the API accepts, distinct from ``core.models.VideoJob`` (the response body).

A separate model rather than reusing ``VideoJob`` for the request too: ``job_id``, ``status``,
``created_at`` and ``segments`` are server-assigned, and ``VideoJob``'s own ``extra="forbid"``
means a client that supplied any of them (even matching the server's own defaults) would be
rejected rather than silently ignored -- the same reasoning that made ``extra="forbid"`` worth
having in the first place applies here too.
"""

from pydantic import BaseModel, ConfigDict

from core.models import DEFAULT_TARGET_DURATION_MS


class JobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    target_duration_ms: int = DEFAULT_TARGET_DURATION_MS
