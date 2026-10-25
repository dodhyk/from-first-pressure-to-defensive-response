"""Meaningful Defensive Movement (MDM) and First Defender Detection module.

Operationalizes the 3-layer evidence hierarchy for qualifying MDM:
1. Movement evidence (speed and displacement from tracking)
2. Defensive context (dynamic-event engagements and attacking context)
3. Temporal and spatial relevance (distance to ball carrier and approach vector)

Determines the First Defender and Episode Start frame strictly without
requiring defensive success or filtering by outcome.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from src.config import PipelineConfig
from src.features import (
    calculate_euclidean_distance,
    calculate_trajectory_speed_and_acceleration,
)

logger = logging.getLogger(__name__)


def evaluate_movement_evidence(
    xs: np.ndarray,
    ys: np.ndarray,
    config: PipelineConfig
) -> Tuple[bool, float, float, float]:
    """Layer 1: Evaluate physical movement evidence from tracking trajectory.

    Returns
    -------
    qualifies : bool
    mean_speed : float
    max_speed : float
    displacement : float
    """
    if len(xs) < 2:
        return False, 0.0, 0.0, 0.0

    speeds, _ = calculate_trajectory_speed_and_acceleration(xs, ys, fps=config.fps)
    max_speed = float(np.max(speeds))
    mean_speed = float(np.mean(speeds))

    disp = calculate_euclidean_distance(xs[0], ys[0], xs[-1], ys[-1])

    # Must exceed speed threshold and displacement
    qualifies = (max_speed >= config.mdm_speed_threshold_mps) and (disp >= config.mdm_displacement_min_m)
    return qualifies, mean_speed, max_speed, disp


def evaluate_defensive_context(
    player_id: int,
    frame_start: int,
    frame_end: int,
    engagements_for_player: List[Dict[str, Any]],
    distance_change_to_ball: float,
    config: PipelineConfig,
    initial_dist_to_ball: Optional[float] = None,
    final_dist_to_ball: Optional[float] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Layer 2: Evaluate tactical context and defensive intent.

    Uses dynamic-event engagements (pressing, pressure, recovery_press, counter_press),
    direct 1v1 containment/jockeying proximity (<= 3.5m), or spatial closing evidence towards the ball carrier.

    Returns
    -------
    qualifies : bool
    context_type : str
    supporting_evidence : dict
    """
    supporting_evidence = {
        "has_engagement_event": False,
        "engagement_subtypes": [],
        "stop_possession_danger": False,
        "reduce_possession_danger": False,
        "force_backward": False,
        "closing_distance_m": float(distance_change_to_ball),
    }

    # Check for overlapping dynamic event engagements
    matching_events = []
    for ev in engagements_for_player:
        ev_start = ev.get("frame_start", 0)
        ev_end = ev.get("frame_end", 0)
        # Check temporal overlap between movement window and engagement event
        if not (frame_end < ev_start or frame_start > ev_end):
            matching_events.append(ev)

    if matching_events:
        supporting_evidence["has_engagement_event"] = True
        subtypes = [ev.get("event_subtype", "engagement") for ev in matching_events]
        supporting_evidence["engagement_subtypes"] = subtypes

        # Record supporting danger reduction indicators without treating them as mandatory success criteria
        for ev in matching_events:
            if ev.get("stop_possession_danger") is True:
                supporting_evidence["stop_possession_danger"] = True
            if ev.get("reduce_possession_danger") is True:
                supporting_evidence["reduce_possession_danger"] = True
            if ev.get("force_backward") is True:
                supporting_evidence["force_backward"] = True

        return True, f"dynamic_event_{subtypes[0]}", supporting_evidence

    # Direct duel / containment context: defender is already in immediate duel / confrontation proximity (<= 3.5m)
    # Jockeying and 1v1 containment at arm's length does not require closing an extra 0.8m when already engaged
    if (initial_dist_to_ball is not None and initial_dist_to_ball <= 3.5) or (final_dist_to_ball is not None and final_dist_to_ball <= 3.5):
        return True, "direct_duel_containment", supporting_evidence

    # Spatial closing context fallback: defender closes distance towards ball carrier
    # (distance_change_to_ball = initial_distance - final_distance > 0)
    if distance_change_to_ball >= config.mdm_distance_closing_min_m:
        return True, "spatial_approach_to_ball", supporting_evidence

    return False, "insufficient_defensive_context", supporting_evidence


def evaluate_spatial_temporal_relevance(
    initial_dist_to_ball: float,
    final_dist_to_ball: float,
    config: PipelineConfig
) -> bool:
    """Layer 3: Evaluate spatial and temporal relevance to the attacking sequence.

    Filters out defenders who are on the opposite side of the pitch (> 25m away)
    and not moving toward the ball carrier or play.
    """
    if initial_dist_to_ball > config.mdm_max_initial_distance_m:
        return False

    # Movement must not be moving drastically away from the ball carrier (> 3m away)
    if (final_dist_to_ball - initial_dist_to_ball) > 3.0:
        return False

    return True


class MDMDetector:
    """Evaluates candidate defender trajectories and selects the First Defender."""

    def __init__(self, config: PipelineConfig, player_registry: Dict[int, Dict[str, Any]]):
        self.config = config
        self.player_registry = player_registry

    def get_candidate_defenders(
        self,
        defending_team_id: int,
        active_player_ids: Set[int]
    ) -> List[int]:
        """Identify eligible outfield defenders on the pitch.

        Excludes goalkeepers and players not currently tracking on the pitch.
        """
        candidates = []
        for pid in active_player_ids:
            p_info = self.player_registry.get(pid, {})
            if p_info.get("team_id") == defending_team_id:
                if not p_info.get("is_goalkeeper", False):
                    candidates.append(pid)
        return candidates

    def find_first_defender_for_episode(
        self,
        candidate_defender_ids: List[int],
        tracking_frames: List[Dict[str, Any]],
        engagements_by_player: Dict[int, List[Dict[str, Any]]],
        ball_carrier_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Identify the First Defender whose qualifying MDM onset starts earliest.

        Parameters
        ----------
        candidate_defender_ids : List[int]
            Eligible defending player IDs.
        tracking_frames : List[Dict[str, Any]]
            Tracking records across the candidate attacking sequence window.
        engagements_by_player : Dict[int, List[Dict[str, Any]]]
            Dynamic on_ball_engagement events grouped by defender ID.
        ball_carrier_id : Optional[int]
            ID of the attacking player in possession.

        Returns
        -------
        first_defender_info : Optional[Dict[str, Any]]
            Dictionary with first_defender_id, onset_frame, mdm_details, etc.
        """
        if not tracking_frames or len(tracking_frames) < self.config.min_trigger_duration_frames:
            return None

        frames_list = [f["frame"] for f in tracking_frames]
        fps = self.config.fps

        # Extract ball carrier trajectory
        ball_positions = {}
        for f in tracking_frames:
            f_num = f["frame"]
            b_data = f.get("ball_data", {})
            if b_data and b_data.get("x") is not None and b_data.get("y") is not None:
                ball_positions[f_num] = (float(b_data["x"]), float(b_data["y"]))
            elif ball_carrier_id:
                for p in f.get("player_data", []):
                    if p.get("player_id") == ball_carrier_id:
                        ball_positions[f_num] = (float(p["x"]), float(p["y"]))
                        break

        # For each candidate defender, check qualifying MDM onset
        qualifying_candidates = []

        for def_id in candidate_defender_ids:
            # Extract defender (x, y) coordinates across frames
            def_frames = []
            def_xs = []
            def_ys = []
            for f in tracking_frames:
                f_num = f["frame"]
                for p in f.get("player_data", []):
                    if p.get("player_id") == def_id:
                        def_frames.append(f_num)
                        def_xs.append(float(p["x"]))
                        def_ys.append(float(p["y"]))
                        break

            if len(def_frames) < 3:
                continue

            xs_arr = np.array(def_xs)
            ys_arr = np.array(def_ys)
            speeds, _ = calculate_trajectory_speed_and_acceleration(xs_arr, ys_arr, fps=fps)

            # Slide over short evaluation windows (e.g., 0.5s = 5 frames) to find earliest qualifying MDM
            win_len = 5
            for i in range(len(def_frames) - win_len + 1):
                sub_xs = xs_arr[i : i + win_len]
                sub_ys = ys_arr[i : i + win_len]
                sub_frames = def_frames[i : i + win_len]

                # Layer 1: Movement evidence
                l1_qualifies, mean_spd, max_spd, disp = evaluate_movement_evidence(sub_xs, sub_ys, self.config)
                if not l1_qualifies:
                    continue

                # Distances to ball
                start_frame = sub_frames[0]
                end_frame = sub_frames[-1]

                b_start = ball_positions.get(start_frame)
                b_end = ball_positions.get(end_frame)
                if not b_start or not b_end:
                    continue

                d_start = calculate_euclidean_distance(sub_xs[0], sub_ys[0], b_start[0], b_start[1])
                d_end = calculate_euclidean_distance(sub_xs[-1], sub_ys[-1], b_end[0], b_end[1])
                closing_dist = d_start - d_end

                # Layer 3: Temporal & spatial relevance
                l3_qualifies = evaluate_spatial_temporal_relevance(d_start, d_end, self.config)
                if not l3_qualifies:
                    continue

                # Layer 2: Defensive context
                player_engagements = engagements_by_player.get(def_id, [])
                l2_qualifies, context_type, supp_evidence = evaluate_defensive_context(
                    def_id, start_frame, end_frame, player_engagements, closing_dist, self.config,
                    initial_dist_to_ball=d_start, final_dist_to_ball=d_end
                )
                if not l2_qualifies:
                    continue

                # All 3 layers satisfied! Record candidate qualifying MDM onset
                qualifying_candidates.append({
                    "player_id": def_id,
                    "player_name": self.player_registry.get(def_id, {}).get("short_name", f"Player {def_id}"),
                    "onset_frame": start_frame,
                    "onset_timestamp": tracking_frames[i].get("timestamp", ""),
                    "mean_speed": mean_spd,
                    "max_speed": max_spd,
                    "displacement": disp,
                    "initial_distance_to_ball": d_start,
                    "final_distance_to_ball": d_end,
                    "closing_distance": closing_dist,
                    "context_type": context_type,
                    "supporting_evidence": supp_evidence,
                })
                # Once earliest qualifying MDM onset is found for this player, move to next player
                break

        if not qualifying_candidates:
            return None

        # Select the candidate who first satisfies the MDM rule.
        # Among near-simultaneous qualifying onsets (within simultaneous_tolerance_frames = 2 frames = 0.20s),
        # prioritize proximity to the ball / ball carrier (point of attack) rather than rewarding a distant sprinter.
        min_onset = min(c["onset_frame"] for c in qualifying_candidates)
        tol_frames = self.config.simultaneous_tolerance_frames
        earliest_tier = [c for c in qualifying_candidates if (c["onset_frame"] - min_onset) <= tol_frames]
        earliest_tier.sort(key=lambda c: (c["initial_distance_to_ball"], c["onset_frame"]))
        return earliest_tier[0]
