from unittest.mock import MagicMock, patch

from lightningfish_coding.seed_enricher import classify_diff_size, enrich_coding_seed
from lightningfish_core.models import EnrichedSeed


def test_classify_diff_size():
    assert classify_diff_size(10) == "xs"
    assert classify_diff_size(100) == "s"
    assert classify_diff_size(400) == "m"
    assert classify_diff_size(900) == "l"
    assert classify_diff_size(2000) == "xl"


def _mock_get(url, **kwargs):
    mock = MagicMock()
    if "/pulls/" in url and "/files" not in url and "/reviews" not in url:
        mock.json.return_value = {
            "title": "Add rate limiting middleware",
            "body": "Closes #42.",
            "additions": 120,
            "deletions": 30,
            "user": {"login": "dev123"},
            "head": {"sha": "abc123"},
            "merged": False,
        }
    elif "/files" in url:
        mock.json.return_value = [
            {"filename": "src/middleware/rate_limit.py"},
            {"filename": "tests/test_rate_limit.py"},
        ]
    elif "search/issues" in url:
        mock.json.return_value = {"total_count": 15}
    else:
        mock.json.return_value = {}
    return mock


def test_enrich_returns_enriched_seed():
    with patch("lightningfish_coding.seed_enricher.requests.get", side_effect=_mock_get):
        result = enrich_coding_seed(
            "https://github.com/owner/repo/pull/42",
            github_token="ghp_test",
        )

    assert isinstance(result, EnrichedSeed)
    assert result.domain_id == "coding"
    assert result.metadata["diff_size_tier"] == "s"
    assert result.metadata["is_test_included"] is True
    assert result.metadata["author_pr_history"] == 15
    assert "python" in result.metadata["languages_touched"]
