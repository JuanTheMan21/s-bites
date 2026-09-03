"""Pure HTTP Range parsing (RFC 7233, single-range only) and a ranged ``Response`` builder.

Kept separate from ``api/artifact_response.py`` so it has no FastAPI routing or ``Storage``
knowledge and is unit-testable directly against plain bytes -- this is what makes a `<video>`
element's seek work against local-disk storage (``DiskStorage``'s ``file://``, ``FakeStorage``'s
``memory://``), the primary day-to-day ``RUNTIME_ENV``, which had no Range support until T24.
"""

from fastapi import Response


def parse_range(range_header: str | None, size: int) -> tuple[int, int] | None:
    """The inclusive ``(start, end)`` byte span ``range_header`` asks for, or ``None`` if it is
    absent, malformed, unsatisfiable, or a multi-range request (unsupported -- falling back to a
    full 200 is always a valid response to a Range request the server chooses not to honor)."""
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes=") :]
    if "," in spec or "-" not in spec:
        return None
    start_str, _, end_str = spec.partition("-")
    try:
        if start_str == "":
            suffix_len = int(end_str)
            if suffix_len <= 0:
                return None
            start, end = max(0, size - suffix_len), size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else size - 1
    except ValueError:
        return None
    end = min(end, size - 1)
    if start < 0 or start > end or start >= size:
        return None
    return start, end


def ranged_response(data: bytes, content_type: str, range_header: str | None) -> Response:
    """A 200 with the full body when ``range_header`` is absent or unsatisfiable as parsed (the
    client falls back correctly either way -- this must stay byte-identical to the pre-Range
    response for a request with no ``Range`` header), or a 206 with exactly the requested span
    and the headers a `<video>` element's seek relies on."""
    size = len(data)
    byte_range = parse_range(range_header, size)
    if byte_range is None:
        return Response(content=data, media_type=content_type, headers={"Accept-Ranges": "bytes"})
    start, end = byte_range
    chunk = data[start : end + 1]
    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(len(chunk)),
    }
    return Response(content=chunk, media_type=content_type, status_code=206, headers=headers)
