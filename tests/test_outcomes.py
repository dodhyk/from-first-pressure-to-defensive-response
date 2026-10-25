"""Unit tests for episode outcome evaluation."""

import pandas as pd
import pytest

from src.config import PipelineConfig
from src.outcomes import OutcomeEvaluator


def test_turnover_evaluation():
    config = PipelineConfig()
    evaluator = OutcomeEvaluator(config)

    # Synthetic events containing possession_loss
    events_df = pd.DataFrame([
        {
            "event_id": "1",
            "event_type": "player_possession",
            "team_id": 1,
            "frame_start": 10,
            "frame_end": 25,
            "end_type": "possession_loss",
        },
        {
            "event_id": "2",
            "event_type": "player_possession",
            "team_id": 2,
            "frame_start": 26,
            "frame_end": 40,
            "end_type": "pass",
        }
    ])

    main_out, det_out, _ = evaluator.evaluate_episode_outcome(
        attacking_team_id=1,
        defending_team_id=2,
        attacking_direction="left_to_right",
        episode_start_frame=15,
        episode_end_frame=25,
        ball_carrier_id=None,
        events_df=events_df,
        tracking_frames=[],
    )

    assert main_out == "TURNOVER"
    assert "TURNOVER" in det_out


def test_progression_evaluation_by_displacement():
    config = PipelineConfig(forward_progression_threshold_m=8.0)
    evaluator = OutcomeEvaluator(config)

    events_df = pd.DataFrame([
        {
            "event_id": "1",
            "event_type": "player_possession",
            "team_id": 1,
            "frame_start": 10,
            "frame_end": 30,
            "end_type": "pass",
        }
    ])

    # Tracking shows ball moving forward by 12m (from x=0 to x=12 in left_to_right)
    tracking = [
        {"frame": 10, "ball_data": {"x": 0.0, "y": 0.0}, "player_data": []},
        {"frame": 30, "ball_data": {"x": 12.0, "y": 2.0}, "player_data": []},
    ]

    main_out, det_out, ev = evaluator.evaluate_episode_outcome(
        attacking_team_id=1,
        defending_team_id=2,
        attacking_direction="left_to_right",
        episode_start_frame=10,
        episode_end_frame=30,
        ball_carrier_id=None,
        events_df=events_df,
        tracking_frames=tracking,
    )

    assert main_out == "PROGRESSION"
    assert ev["forward_displacement_m"] == pytest.approx(12.0)
