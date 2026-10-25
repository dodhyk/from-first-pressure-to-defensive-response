"""Unit tests for MDM evaluation and First Defender selection."""

import numpy as np
import pytest

from src.config import PipelineConfig
from src.mdm_detector import (
    MDMDetector,
    evaluate_defensive_context,
    evaluate_movement_evidence,
    evaluate_spatial_temporal_relevance,
)


def test_evaluate_movement_evidence():
    config = PipelineConfig()
    # Fast displacement: 2 m in 0.4s (4 frames at 10 FPS = 5 m/s)
    xs = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    ys = np.zeros_like(xs)

    qualifies, mean_spd, max_spd, disp = evaluate_movement_evidence(xs, ys, config)
    assert qualifies is True
    assert max_spd >= config.mdm_speed_threshold_mps
    assert disp >= config.mdm_displacement_min_m


def test_evaluate_movement_evidence_slow():
    config = PipelineConfig()
    # Slow drift: 0.2m in 0.4s (0.5 m/s)
    xs = np.array([0.0, 0.05, 0.1, 0.15, 0.2])
    ys = np.zeros_like(xs)

    qualifies, _, max_spd, _ = evaluate_movement_evidence(xs, ys, config)
    assert qualifies is False


def test_evaluate_spatial_temporal_relevance():
    config = PipelineConfig()
    # Defender starts 15m away, closes to 12m -> qualifies
    assert evaluate_spatial_temporal_relevance(15.0, 12.0, config) is True

    # Defender starts > 25m away -> rejected
    assert evaluate_spatial_temporal_relevance(30.0, 27.0, config) is False

    # Defender moves away by > 3m -> rejected
    assert evaluate_spatial_temporal_relevance(15.0, 19.0, config) is False


def test_first_defender_selection():
    config = PipelineConfig()
    players = {
        101: {"id": 101, "short_name": "Def A", "team_id": 2, "is_goalkeeper": False},
        102: {"id": 102, "short_name": "Def B", "team_id": 2, "is_goalkeeper": False},
        100: {"id": 100, "short_name": "GK", "team_id": 2, "is_goalkeeper": True},
    }
    detector = MDMDetector(config, players)

    # Check goalkeeper exclusion
    candidates = detector.get_candidate_defenders(defending_team_id=2, active_player_ids={100, 101, 102})
    assert 100 not in candidates
    assert set(candidates) == {101, 102}
