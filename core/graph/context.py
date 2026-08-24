"""What a graph run needs from the outside world, without naming who provides it.

Deliberately its own type rather than a reuse of ``config.Adapters``. ``config.py`` is allowed to
know about ``core/graph/`` -- it is the resolver, and resolving into whatever shape the graph
wants is exactly its job -- but the reverse would tie ``core/`` to the concrete resolver module,
which is precisely the dependency direction the boundary rule forbids. Five fields, not six:
``JobQueue`` is deliberately absent. Driving the queue -- claiming a job, completing or failing
it -- is a runner's job, wrapping a whole graph invocation from the outside. Nothing inside one
run's nodes touches it.
"""

from dataclasses import dataclass
from pathlib import Path

from interfaces import LLMProvider, RenderBackend, SkillRegistry, Storage, TTSProvider


@dataclass(frozen=True)
class GraphContext:
    """Injected into every node via LangGraph's ``Runtime[GraphContext]``.

    ``working_dir`` is where a node writes real files before durably persisting them through
    ``storage`` -- ``TTSProvider.synthesize`` takes a filesystem ``Path`` (D21), not a storage
    key, so something has to say where that path lives.

    ``frame_budget`` and ``fps`` are the edge-read rendering configuration
    ``core/frame_budget.py`` anticipates: ``FRAME_BUDGET`` and ``FPS`` live in the environment and
    arrive here as parameters, so neither this module nor ``core/tier_resolver.py`` learns that
    those names exist. ``frame_budget`` is the *base* -- what a ``DEFAULT_TARGET_DURATION_MS``
    video gets -- and ``core.frame_budget.scale_frame_budget`` turns it into the budget for the
    length actually requested.

    They belong here rather than on ``GraphState`` on purpose: context is re-supplied on every
    invocation, so a resumed run picks up the current configuration, where a checkpointed state
    channel would pin it to whatever the run first started with.
    """

    llm: LLMProvider
    tts: TTSProvider
    storage: Storage
    skills: SkillRegistry
    render: RenderBackend
    working_dir: Path
    frame_budget: int
    fps: int
