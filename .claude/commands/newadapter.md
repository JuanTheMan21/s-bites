---
description: Scaffold a new adapter implementing an existing interface
argument-hint: <interface> <name>
---

Scaffold an adapter named **$2** implementing the **$1** interface.

1. Read `interfaces/$1` and reproduce its signatures **exactly** — parameter names, types, return
   types, and raised exceptions. A signature that drifts from the interface defeats the entire
   point of having one.
2. Read the existing implementations of `$1` in `adapters/local/` and `adapters/azure/` and match
   their conventions and error handling.
3. Create the adapter in the correct directory: `adapters/local/` or `adapters/azure/`.
4. Register it in `config.py`, reading any settings from environment variables. Add the new
   variables to `.env.example` with a comment explaining what each does.
5. Add a parity test asserting this implementation agrees with its counterpart on semantics — not
   just that it satisfies the ABC, but that it returns the same shapes, units, and error behavior.

Retry, backoff, rate limiting, and vendor-specific quirks all belong **in the adapter**. Nothing
about this adapter may require a change in `core/`. If it seems to, the interface is wrong — raise
that rather than working around it.

Leave method bodies as `NotImplementedError` with a TODO if this is a deliberate stub. A stub with
correct signatures is useful; a stub with invented signatures is worse than nothing.
