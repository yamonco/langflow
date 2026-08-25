import importlib.util
from pathlib import Path

module_path = Path(__file__).parents[3] / "src/backend/langflow/components/custom_components/facebook_metrics.py"
spec = importlib.util.spec_from_file_location("facebook_metrics", module_path)
facebook_metrics = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(facebook_metrics)
extract_og_view_count = facebook_metrics.extract_og_view_count
extract_provider_view_count = facebook_metrics.extract_provider_view_count
is_facebook_video = facebook_metrics.is_facebook_video
parse_view_count = facebook_metrics.parse_view_count


def test_parse_view_count_normalizes_facebook_abbreviations():
    assert parse_view_count("조회 8.9만회") == 89_000
    assert parse_view_count("75K views") == 75_000
    assert parse_view_count("75K") == 75_000
    assert parse_view_count("8.9만") == 89_000
    assert parse_view_count("0 views") == 0
    assert parse_view_count(0) == 0


def test_parse_view_count_distinguishes_absent_and_invalid_values():
    assert parse_view_count(None) is None
    assert parse_view_count("조회수 없음") is None


def test_extract_og_view_count_reads_facebook_metadata_only():
    assert extract_og_view_count('<meta property="og:title" content="브랜드 | 조회 8.9만회">') == 89_000
    assert extract_og_view_count('<meta content="75K views" property="og:title">') == 75_000
    assert extract_og_view_count('<meta property="og:description" content="75K views">') is None


def test_provider_view_count_is_normalized_without_losing_zero():
    assert extract_provider_view_count({"play_count": "75K"}) == 75_000
    assert extract_provider_view_count({"play_count": 0, "video_view_count": "75K"}) == 0
    assert extract_provider_view_count({"play_count": None, "video_view_count": "8.9만"}) == 89_000
    assert extract_provider_view_count({}) is None


def test_facebook_metadata_fallback_is_limited_to_video_content():
    assert is_facebook_video("https://www.facebook.com/reel/2145090576412773")
    assert is_facebook_video("https://www.facebook.com/brand/videos/123")
    assert is_facebook_video("https://www.facebook.com/brand/posts/123", [{"type": "video"}])
    assert not is_facebook_video("https://www.facebook.com/brand/posts/123")
