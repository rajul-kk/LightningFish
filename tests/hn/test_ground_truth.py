import time
from unittest.mock import MagicMock, patch

from lightningfish_hn.ground_truth import (
    COMMENTS_HIGH,
    COMMENTS_LOW,
    POINTS_HIGH,
    POINTS_LOW,
    get_hn_ground_truth,
)


def _mock_get_with_age(age_seconds):
    def _get(url, **kwargs):
        mock = MagicMock()
        mock.json.return_value = {"hits": [{
            "points": 87, "num_comments": 42,
            "created_at_i": int(time.time()) - age_seconds,
        }]}
        return mock
    return _get


def test_returns_none_for_story_younger_than_24h():
    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get_with_age(3600)):
        assert get_hn_ground_truth(1) is None


def test_returns_ground_truth_for_settled_story():
    with patch("lightningfish_hn.seed_enricher.requests.get", side_effect=_mock_get_with_age(48 * 3600)):
        truth = get_hn_ground_truth(1)
    assert truth is not None
    assert truth.data["points"] == 87
    assert truth.data["num_comments"] == 42


def test_threshold_constants_have_a_gap():
    # LOW <= x < HIGH is the deliberate "no signal" band (truth_direction
    # returns 0 there, skipped by the backtest rather than tie-broken).
    assert POINTS_LOW < POINTS_HIGH
    assert COMMENTS_LOW < COMMENTS_HIGH
