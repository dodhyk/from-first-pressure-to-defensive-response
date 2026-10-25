"""Unit tests for URL generation, data loading, error handling, and schema validation."""

from pathlib import Path
import pytest
import requests

from src.data_loader import (
    get_events_url,
    get_metadata_url,
    get_tracking_url,
    download_file,
    DataLoader,
)


def test_url_generation():
    """Verify dynamic URL construction for arbitrary match IDs."""
    match_id = 999123
    meta_url = get_metadata_url(match_id)
    events_url = get_events_url(match_id)
    track_url = get_tracking_url(match_id)

    assert meta_url == "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/999123/999123_match.json"
    assert events_url == "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/999123/999123_dynamic_events.csv"
    assert track_url == "https://media.githubusercontent.com/media/SkillCorner/opendata/master/data/matches/999123/999123_tracking_extrapolated.jsonl"


def test_download_file_nonexistent_404(tmp_path):
    """Verify error handling on non-existent match resource (HTTP 404 or offline connection error)."""
    invalid_url = "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/0000000/0000000_match.json"
    dest = tmp_path / "test.json"

    with pytest.raises(Exception) as exc_info:
        download_file(invalid_url, dest, force=True, timeout=10)

    assert not dest.exists()


def test_download_caching(tmp_path):
    """Verify that cached files are reused and not redownloaded unless forced."""
    sample_file = tmp_path / "cached_sample.txt"
    sample_file.write_text("pre-existing cached content", encoding="utf-8")

    # Should not touch or overwrite the existing cached file
    result = download_file("http://example.com/fake.txt", sample_file, force=False)
    assert result == sample_file
    assert sample_file.read_text(encoding="utf-8") == "pre-existing cached content"
