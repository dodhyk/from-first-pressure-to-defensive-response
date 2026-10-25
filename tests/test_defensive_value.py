"""Unit tests for EPV extraction and Defensive Value (DV) convention."""

import pandas as pd
import pytest

from src.config import PipelineConfig
from src.defensive_value import DefensiveValueCalculator


def test_defensive_value_sign_convention():
    """Verify that DV = EPV_against_start - EPV_against_end.

    Positive DV means opponent's attacking threat decreased (good defense).
    Negative DV means opponent's attacking threat increased (attack progressed).
    """
    config = PipelineConfig()
    calc = DefensiveValueCalculator(config)

    # Opponent threat decreased from 0.05 to 0.01 (threat reduced)
    events_df = pd.DataFrame([
        {
            "event_id": "1",
            "event_type": "player_possession",
            "team_id": 1,
            "frame_start": 100,
            "frame_end": 150,
            "possession_epv_against_start": 0.05,
            "possession_epv_against_end": 0.01,
        }
    ])

    epv_start, epv_end, dv, prov = calc.calculate_defensive_value(
        attacking_team_id=1,
        episode_start_frame=110,
        episode_end_frame=140,
        events_df=events_df,
    )

    assert epv_start == pytest.approx(0.05)
    assert epv_end == pytest.approx(0.01)
    assert dv == pytest.approx(0.04)  # Positive DV
    assert prov["epv_missing_status"] == "available"


def test_defensive_value_negative_progression():
    """Verify that when opponent threat increases, DV is negative."""
    config = PipelineConfig()
    calc = DefensiveValueCalculator(config)

    # Opponent threat increased from 0.02 to 0.08
    events_df = pd.DataFrame([
        {
            "event_id": "1",
            "event_type": "player_possession",
            "team_id": 1,
            "frame_start": 100,
            "frame_end": 150,
            "possession_epv_against_start": 0.02,
            "possession_epv_against_end": 0.08,
        }
    ])

    epv_start, epv_end, dv, _ = calc.calculate_defensive_value(
        attacking_team_id=1,
        episode_start_frame=110,
        episode_end_frame=140,
        events_df=events_df,
    )

    assert dv == pytest.approx(-0.06)  # Negative DV


def test_missing_epv_handling():
    config = PipelineConfig()
    calc = DefensiveValueCalculator(config)

    # Events dataframe without EPV columns
    events_df = pd.DataFrame([
        {
            "event_id": "1",
            "event_type": "player_possession",
            "team_id": 1,
            "frame_start": 100,
            "frame_end": 150,
        }
    ])

    epv_start, epv_end, dv, prov = calc.calculate_defensive_value(
        attacking_team_id=1,
        episode_start_frame=110,
        episode_end_frame=140,
        events_df=events_df,
    )

    assert dv is None
    assert prov["epv_missing_status"] == "columns_not_present_in_events"
