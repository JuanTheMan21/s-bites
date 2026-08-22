"""How a fake is made to fail on purpose.

An in-memory fake succeeds at everything, which is the problem with it. ``JobQueue`` documents
``ProviderUnavailable`` and ``RateLimited`` on the class rather than per method precisely because
the in-process implementation never raises either -- so code written against the local pool alone
has never seen them, and T34 is where that bill arrives. The same holds everywhere: T14's retry
classifier cannot be tested against adapters that only ever work.

So every fake inherits this and calls ``self._maybe_fail("<method>")`` on entry. A test arms a
failure, the next call raises it, and the fake is otherwise untouched::

    queue.fail_next("dequeue", RateLimited("throttled"))
    assert await queue.dequeue() is None   # raises RateLimited instead

One mechanism shared by all six rather than six slightly different ones, because a fake that
fails differently from its siblings is a fake nobody trusts.
"""


class FailureInjector:
    """Arms exceptions for named methods to raise on their next call."""

    def fail_next(self, method: str, exc: Exception, *, times: int = 1) -> None:
        """Make the next ``times`` calls to ``method`` raise ``exc``, then behave normally.

        Raises ``AttributeError`` if ``method`` is not a real method on this fake. A typo would
        otherwise arm a failure that never fires, and the test would pass for the wrong reason.
        """
        if not callable(getattr(self, method, None)):
            raise AttributeError(f"{type(self).__name__} has no method {method!r} to fail")
        if times < 1:
            raise ValueError(f"times must be at least 1, got {times}")
        self._armed.setdefault(method, []).extend([exc] * times)

    @property
    def _armed(self) -> dict[str, list[Exception]]:
        # Created on first use rather than in __init__, so no fake can break by forgetting to
        # call super().__init__() -- a failure that would show up as a confusing AttributeError
        # in whichever test happened to arm something first.
        store: dict[str, list[Exception]] | None = getattr(self, "_armed_failures", None)
        if store is None:
            store = {}
            self._armed_failures: dict[str, list[Exception]] = store
        return store

    def _maybe_fail(self, method: str) -> None:
        """Raise and consume one armed failure for ``method``, if any is waiting."""
        pending = self._armed.get(method)
        if pending:
            raise pending.pop(0)
