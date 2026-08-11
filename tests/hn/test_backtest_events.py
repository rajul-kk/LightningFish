from unittest.mock import MagicMock, patch

from lightningfish_hn.backtest_events import pull_hn_events


def _search_by_date_response(ids):
    mock = MagicMock()
    mock.json.return_value = {"hits": [{"objectID": str(i)} for i in ids]}
    return mock


def _item_response(story_id, points=50, num_comments=25):
    mock = MagicMock()
    mock.json.return_value = {"hits": [{
        "title": f"Story {story_id}", "story_text": "", "url": "https://example.com",
        "author": "someone", "created_at": "2026-01-01T00:00:00.000Z",
        "created_at_i": 1767225600, "_tags": ["story"],
        "points": points, "num_comments": num_comments, "objectID": str(story_id),
    }]}
    return mock


def _make_get(call_order):
    def _get(url, **kwargs):
        if "search_by_date" in url:
            call_order.append("date")
            ids = [1, 2, 3] if len(call_order) == 1 else [4, 5, 6]
            return _search_by_date_response(ids)
        if "/users/" in url:
            m = MagicMock()
            m.json.return_value = {"karma": 100}
            return m
        params = kwargs.get("params", {})
        story_id = str(params.get("tags", "story_0")).split("_")[-1]
        return _item_response(story_id)
    return _get


def test_pull_hn_events_returns_class_balanced_set():
    call_order: list[str] = []
    get_fn = _make_get(call_order)
    with patch("lightningfish_hn.backtest_events.requests.get", side_effect=get_fn), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=get_fn):
        events = pull_hn_events(metric="points", limit=6)

    assert len(events) == 6
    assert {e.event_id for e in events} == {"hn:1", "hn:2", "hn:3", "hn:4", "hn:5", "hn:6"}


def test_pull_hn_events_interleaves_high_and_low():
    call_order: list[str] = []
    get_fn = _make_get(call_order)
    with patch("lightningfish_hn.backtest_events.requests.get", side_effect=get_fn), \
         patch("lightningfish_hn.seed_enricher.requests.get", side_effect=get_fn):
        events = pull_hn_events(metric="num_comments", limit=6)

    # First id comes from the "high" search (ids 1,2,3), second from "low" (4,5,6).
    assert events[0].event_id == "hn:1"
    assert events[1].event_id == "hn:4"


def test_pull_hn_events_rejects_unknown_metric():
    try:
        pull_hn_events(metric="upvotes")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
