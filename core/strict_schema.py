"""The base class for every model the LLM is asked to fill.

Azure OpenAI's *strict* structured-output mode constrains generation so the model cannot emit
a token that violates the schema -- the response is valid by construction rather than valid on
inspection. The price is that Azure rejects outright any schema using a keyword outside a small
supported subset, and a rejected schema is a 400 at call time rather than a validation error.
It surfaces in the middle of a run, not at import.

The rules, and what each means for how models here are written:

**Every property must appear in** ``required``. Pydantic drops a field from ``required`` the
moment it has a default, so *a default is what breaks strict mode*. Optionality is expressed as
a required-but-nullable field -- ``str | None`` with no default -- because strict mode has no
notion of an absent key. "There is no subtitle" has to be sendable as an explicit ``null``.

**``additionalProperties: false`` on every object**, nested ones included. That is what this
base class provides. A nested model that forgets to inherit it fails the conformance test in
``tests/test_slot_schemas.py`` instead of failing at Azure.

**No constraint keywords.** ``minLength``, ``maxLength``, ``pattern``, ``format``, ``minimum``,
``maximum``, ``multipleOf``, ``minItems``, ``maxItems`` and ``uniqueItems`` are unsupported, so
``Field(max_length=60)`` on a headline does not make the schema stricter -- it makes it
rejected. Guidance that would have lived in a constraint goes into ``Field(description=...)``
prose, which *is* supported and is the only channel for telling the model what a slot means.
Where a value genuinely must be bounded, use an ``Enum``: enums survive strict mode, ranges do
not. ``Importance`` in ``core/models.py`` is that trade made deliberately.

**The root must be an object.** A call that wants a list asks for a model wrapping one.

Inheriting this class is also the *marker* that a model is LLM-facing: the conformance test
enumerates subclasses recursively, so a schema added in T15 or T16 is checked by virtue of
existing, without anyone remembering to register it.
"""

from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    """A pydantic model whose JSON Schema satisfies Azure strict structured-output mode.

    Inherit this for anything passed as ``LLMProvider.generate``'s ``schema``, and for every
    model nested inside one. Do **not** inherit it for pipeline state: ``Segment`` and
    ``VideoJob`` are ours to fill, carry defaults, and would fail the conformance test for
    good reason.
    """

    model_config = ConfigDict(extra="forbid")
