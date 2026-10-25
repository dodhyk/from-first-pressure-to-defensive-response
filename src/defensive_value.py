"""Defensive Value (DV) and Expected Possession Value (EPV) calculation module.

Operationalizes the agreed research convention:
DV = EPV_against_start - EPV_against_end

Positive DV indicates the defensive sequence reduced the opponent's attacking value.
Negative DV indicates the opponent's attacking value increased.

Extracts official SkillCorner dynamic-event EPV metrics with full provenance.
"""

import logging
from typing import Any, Dict, Optional, Tuple
import pandas as pd

from src.config import PipelineConfig

logger = logging.getLogger(__name__)


class DefensiveValueCalculator:
    """Extracts EPV values from dynamic events and computes Defensive Value (DV)."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def calculate_defensive_value(
        self,
        attacking_team_id: int,
        episode_start_frame: int,
        episode_end_frame: int,
        events_df: pd.DataFrame,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Dict[str, str]]:
        """Calculate Defensive Value for an episode.

        Returns
        -------
        epv_start : Optional[float]
        epv_end : Optional[float]
        defensive_value : Optional[float]
        provenance : Dict[str, str]
            epv_source, epv_method, epv_missing_status
        """
        provenance = {
            "epv_source": "official_skillcorner_dynamic_events",
            "epv_method": "possession_epv_against",
            "epv_missing_status": "missing_in_dataset",
        }

        # Look for player possession events for the attacking team overlapping the episode
        relevant_possessions = events_df[
            (events_df["event_type"] == "player_possession") &
            (events_df["team_id"] == attacking_team_id) &
            (events_df["frame_start"] <= episode_end_frame + 20) &
            (events_df["frame_end"] >= episode_start_frame - 20)
        ]

        if relevant_possessions.empty:
            return None, None, None, provenance

        # Check for official EPV against columns
        start_col = "possession_epv_against_start"
        end_col = "possession_epv_against_end"

        if start_col not in relevant_possessions.columns or end_col not in relevant_possessions.columns:
            provenance["epv_missing_status"] = "columns_not_present_in_events"
            return None, None, None, provenance

        # Find the possession event closest to episode_start_frame
        relevant_possessions = relevant_possessions.copy()
        relevant_possessions["dist_to_start"] = (relevant_possessions["frame_start"] - episode_start_frame).abs()
        relevant_possessions["dist_to_end"] = (relevant_possessions["frame_end"] - episode_end_frame).abs()

        sorted_by_start = relevant_possessions.dropna(subset=[start_col]).sort_values("dist_to_start")
        sorted_by_end = relevant_possessions.dropna(subset=[end_col]).sort_values("dist_to_end")

        if sorted_by_start.empty or sorted_by_end.empty:
            provenance["epv_missing_status"] = "values_nan_in_matched_possession"
            return None, None, None, provenance

        epv_start_val = sorted_by_start.iloc[0][start_col]
        epv_end_val = sorted_by_end.iloc[0][end_col]

        if pd.isna(epv_start_val) or pd.isna(epv_end_val):
            provenance["epv_missing_status"] = "values_nan_in_matched_possession"
            return None, None, None, provenance

        epv_start = float(epv_start_val)
        epv_end = float(epv_end_val)

        # Locked Research Decision convention:
        # DV = EPV_against_start - EPV_against_end
        defensive_value = epv_start - epv_end
        provenance["epv_missing_status"] = "available"

        return epv_start, epv_end, defensive_value, provenance
