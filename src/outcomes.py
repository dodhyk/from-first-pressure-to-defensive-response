"""Outcome classification and tactical outcome evaluation for defensive episodes.

Implements two-level outcome classification:
1. Main outcome: PROGRESSION, NO_PROGRESSION, TURNOVER, UNRESOLVED.
2. Detailed outcome: verified granular categories supported by dynamic-event and tracking evidence.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.config import PipelineConfig

logger = logging.getLogger(__name__)


class OutcomeEvaluator:
    """Evaluates main and detailed outcomes of defensive episodes."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def evaluate_episode_outcome(
        self,
        attacking_team_id: int,
        defending_team_id: int,
        attacking_direction: str,  # 'left_to_right' or 'right_to_left'
        episode_start_frame: int,
        episode_end_frame: int,
        ball_carrier_id: Optional[int],
        events_df: pd.DataFrame,
        tracking_frames: List[Dict[str, Any]],
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Determine main and detailed outcome of the defensive episode.

        Parameters
        ----------
        attacking_team_id : int
            Team ID on attack.
        defending_team_id : int
            Team ID on defense.
        attacking_direction : str
            'left_to_right' (+x is forward) or 'right_to_left' (-x is forward).
        episode_start_frame : int
        episode_end_frame : int
        ball_carrier_id : Optional[int]
        events_df : pd.DataFrame
            Dynamic events table for the match.
        tracking_frames : List[Dict[str, Any]]
            Tracking frames from start to end of episode.

        Returns
        -------
        main_outcome : str
            PROGRESSION, NO_PROGRESSION, TURNOVER, UNRESOLVED
        detailed_outcome : str
        evidence_dict : Dict[str, Any]
        """
        evidence: Dict[str, Any] = {
            "attacking_direction": attacking_direction,
            "forward_displacement_m": 0.0,
            "has_line_break": False,
            "has_shot": False,
            "has_possession_loss": False,
            "turnover_verified": False,
            "event_end_type": None,
        }

        # Filter events overlapping the episode window
        # Allow small buffer around episode_end_frame to capture immediate result of defensive action
        buffer_frames = self.config.post_possession_loss_buffer_frames
        sub_events = events_df[
            (events_df["frame_start"] <= episode_end_frame + buffer_frames) &
            (events_df["frame_end"] >= episode_start_frame)
        ]

        # 1. Check for Turnovers
        # Find player possession events for the attacking team within this phase
        att_possessions = sub_events[
            (sub_events["event_type"] == "player_possession") &
            (sub_events["team_id"] == attacking_team_id)
        ]

        # Check subsequent possession by defending team
        def_possessions = sub_events[
            (sub_events["event_type"] == "player_possession") &
            (sub_events["team_id"] == defending_team_id) &
            (sub_events["frame_start"] >= episode_start_frame)
        ]

        # Check explicit possession loss end_types
        has_possession_loss = False
        loss_end_types = []
        for _, row in att_possessions.iterrows():
            end_t = str(row.get("end_type", "")).lower()
            if end_t in ["possession_loss", "clearance"]:
                has_possession_loss = True
                loss_end_types.append(end_t)

        # Check defensive recovery engagements
        def_engagements = sub_events[
            (sub_events["event_type"] == "on_ball_engagement") &
            (sub_events["team_id"] == defending_team_id)
        ]

        # Verify turnover: possession loss accompanied by defensive sequence or subsequent defending possession
        if (has_possession_loss and len(def_possessions) > 0) or ("possession_loss" in loss_end_types):
            evidence["has_possession_loss"] = True
            evidence["turnover_verified"] = True
            # Detailed turnover classification
            if any(ev.get("event_subtype") in ["pressing", "recovery_press"] for _, ev in def_engagements.iterrows()):
                return "TURNOVER", "TURNOVER_TACKLE_OR_CHALLENGE", evidence
            return "TURNOVER", "TURNOVER_POSSESSION_LOSS", evidence

        # 2. Check for Shots / Danger Zone Entries
        for _, row in att_possessions.iterrows():
            if str(row.get("end_type", "")).lower() == "shot":
                evidence["has_shot"] = True
                return "PROGRESSION", "PROGRESSION_SHOT", evidence

        # Check line breaks in attacking events
        line_break_cols = ["first_line_break", "second_last_line_break", "last_line_break"]
        for col in line_break_cols:
            if col in sub_events.columns:
                breaks = sub_events[sub_events[col] == True]
                if len(breaks) > 0:
                    evidence["has_line_break"] = True
                    return "PROGRESSION", "PROGRESSION_LINE_BREAK", evidence

        # 3. Spatial Displacement Analysis from Tracking
        # Calculate forward distance gained along the attacking axis
        if tracking_frames and len(tracking_frames) >= 2:
            first_f = tracking_frames[0]
            last_f = tracking_frames[-1]

            ball_start = first_f.get("ball_data", {})
            ball_end = last_f.get("ball_data", {})

            b_xs = ball_start.get("x")
            b_xe = ball_end.get("x")

            # Fallback to ball carrier position if ball tracking absent
            if b_xs is None and ball_carrier_id:
                for p in first_f.get("player_data", []):
                    if p.get("player_id") == ball_carrier_id:
                        b_xs = p.get("x")
                        break
            if b_xe is None and ball_carrier_id:
                for p in last_f.get("player_data", []):
                    if p.get("player_id") == ball_carrier_id:
                        b_xe = p.get("x")
                        break

            if b_xs is not None and b_xe is not None:
                if attacking_direction == "left_to_right":
                    forward_gain = float(b_xe - b_xs)
                else:  # right_to_left
                    forward_gain = float(b_xs - b_xe)

                evidence["forward_displacement_m"] = forward_gain

                # Check progression threshold
                if forward_gain >= self.config.forward_progression_threshold_m:
                    return "PROGRESSION", "PROGRESSION_TERRITORIAL_GAIN", evidence
                elif forward_gain <= -2.0:
                    # Forced backward pass / recycle
                    return "NO_PROGRESSION", "NO_PROGRESSION_RECYCLED_BACK", evidence
                else:
                    return "NO_PROGRESSION", "NO_PROGRESSION_LATERAL_OR_STALLED", evidence

        # If data is insufficient to establish outcome
        return "UNRESOLVED", "UNRESOLVED_INSUFFICIENT_EVIDENCE", evidence
