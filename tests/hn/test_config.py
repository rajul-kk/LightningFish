from lightningfish_core.models import EnrichedSeed, GroundTruthRecord
from lightningfish_hn.config import HNCommentsAdapter, HNDomainAdapter


def _seed(metadata):
    return EnrichedSeed(
        domain_id="hn", raw_input={}, summary="s", entities=[], event_type="story",
        metadata=metadata,
    )


def test_domain_attributes():
    a = HNDomainAdapter()
    assert a.domain_id == "hn"
    assert a.opinion_labels == ("flop", "viral")
    assert len(a.argument_taxonomy()) == 8


def test_cache_key():
    a = HNDomainAdapter()
    assert a.cache_key(_seed({"story_id": 42})) == "hn:42"
    assert a.cache_key(_seed({})) is None


def test_points_naive_prediction_and_truth_direction():
    a = HNDomainAdapter()
    established = _seed({"author_karma": 5000, "url": "https://example.com"})
    assert a.naive_prediction(established) > 0
    unknown = _seed({"author_karma": 0, "url": ""})
    assert a.naive_prediction(unknown) < 0

    assert a.truth_direction(GroundTruthRecord(data={"points": 100})) == 1
    assert a.truth_direction(GroundTruthRecord(data={"points": 5})) == -1
    assert a.truth_direction(GroundTruthRecord(data={"points": 20})) == 0  # gap zone


def test_naive_prediction_never_ties_when_signals_disagree():
    a = HNDomainAdapter()
    karma_no_url = _seed({"author_karma": 5000, "url": ""})
    assert a.naive_prediction(karma_no_url) != 0
    url_no_karma = _seed({"author_karma": 0, "url": "https://example.com"})
    assert a.naive_prediction(url_no_karma) != 0


def test_comments_adapter_scores_num_comments_not_points():
    a = HNCommentsAdapter()
    truth = GroundTruthRecord(data={"points": 5, "num_comments": 100})
    # Would be -1 under points-direction (points=5 < POINTS_LOW), but the
    # comments adapter reads num_comments instead.
    assert a.truth_direction(truth) == 1


def test_comments_adapter_naive_prediction_uses_ask_and_question_heuristic():
    a = HNCommentsAdapter()
    ask_with_question = _seed({"tag": "ask_hn", "title": "What's your favorite tool?"})
    assert a.naive_prediction(ask_with_question) > 0
    plain_link = _seed({"tag": "story", "title": "A new database"})
    assert a.naive_prediction(plain_link) < 0
