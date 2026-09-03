"""T24: Range parsing and the ranged response, against plain bytes -- no FastAPI app, no
Storage. This is the closest thing to a spec for RFC 7233 support this project has."""

from api.byte_range import parse_range, ranged_response


def test_no_range_header_returns_none() -> None:
    assert parse_range(None, 100) is None
    assert parse_range("", 100) is None


def test_a_bounded_range_parses() -> None:
    assert parse_range("bytes=0-9", 100) == (0, 9)
    assert parse_range("bytes=10-19", 100) == (10, 19)


def test_an_open_ended_range_extends_to_the_last_byte() -> None:
    assert parse_range("bytes=90-", 100) == (90, 99)


def test_a_suffix_range_counts_from_the_end() -> None:
    assert parse_range("bytes=-10", 100) == (90, 99)


def test_an_end_past_the_size_clamps_to_the_last_byte() -> None:
    assert parse_range("bytes=0-999", 100) == (0, 99)


def test_unsatisfiable_and_malformed_ranges_are_none() -> None:
    assert parse_range("bytes=200-300", 100) is None  # start beyond size
    assert parse_range("bytes=50-10", 100) is None  # end before start
    assert parse_range("bytes=abc-def", 100) is None
    assert parse_range("bytes=0-10,20-30", 100) is None  # multi-range, unsupported
    assert parse_range("not-bytes=0-10", 100) is None


def test_no_range_header_is_a_full_200_identical_to_pre_range_behaviour() -> None:
    data = b"0123456789"
    resp = ranged_response(data, "video/mp4", None)
    assert resp.status_code == 200
    assert resp.body == data
    assert resp.headers["accept-ranges"] == "bytes"
    assert "content-range" not in resp.headers


def test_an_unsatisfiable_range_falls_back_to_a_full_200() -> None:
    data = b"0123456789"
    resp = ranged_response(data, "video/mp4", "bytes=999-1000")
    assert resp.status_code == 200
    assert resp.body == data


def test_a_satisfiable_range_returns_206_with_exactly_that_chunk() -> None:
    data = b"0123456789"
    resp = ranged_response(data, "video/mp4", "bytes=2-4")
    assert resp.status_code == 206
    assert resp.body == b"234"
    assert resp.headers["content-range"] == "bytes 2-4/10"
    assert resp.headers["content-length"] == "3"
    assert resp.headers["accept-ranges"] == "bytes"


def test_a_suffix_range_returns_the_tail_chunk() -> None:
    data = b"0123456789"
    resp = ranged_response(data, "video/mp4", "bytes=-3")
    assert resp.status_code == 206
    assert resp.body == b"789"
    assert resp.headers["content-range"] == "bytes 7-9/10"
