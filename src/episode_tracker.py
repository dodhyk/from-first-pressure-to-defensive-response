"""Episode Tracker and Post-Start Defensive Movement Analyzer.

Implements the fundamental locked research decisions:
1. Observes all post-start defensive movements WITHOUT an MDM or success filter.
2. Distinguishes genuine movement onsets from pre-existing movement continuations.
3. Identifies Second Defender and preserves simultaneous responders within configurable tolerance.
4. Classifies Supporting Defenders.
5. Computes episode-level coordination metrics (inter-defender distances, compactness changes, reaction times).
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from src.config import PipelineConfig
from src.features import (
    calculate_defensive_line_x,
    calculate_euclidean_distance,
    calculate_movement_direction,
    calculate_team_compactness,
    calculate_trajectory_speed_and_acceleration,
    detect_movement_segments,
    vector_alignment,
)
from src.schema import DefenderMovementRecord, EpisodeDefenderFeatures

logger = logging.getLogger(__name__)


class EpisodeTracker:
    """Tracks post-start defensive movements and extracts coordination features."""

    def __init__(self, config: PipelineConfig, player_registry: Dict[int, Dict[str, Any]]):
        self.config = config
        self.player_registry = player_registry

    def track_defenders(
        self,
        episode_id: str,
        match_id: int,
        defending_team_id: int,
        first_defender_info: Dict[str, Any],
        episode_start_frame: int,
        episode_end_frame: int,
        tracking_index: Dict[int, Dict[str, Any]],
        defending_direction: str = "left_to_right",
    ) -> Tuple[List[DefenderMovementRecord], Dict[str, Any], EpisodeDefenderFeatures]:
        """Track and classify all defensive movements occurring within an episode.

        Distinguishes pre-existing movement from new movement onsets by inspecting
        a pre-start tracking window (e.g. 5 frames before episode start).

        Parameters
        ----------
        episode_id : str
        match_id : int
        defending_team_id : int
        first_defender_info : Dict[str, Any]
        episode_start_frame : int
        episode_end_frame : int
        tracking_index : Dict[int, Dict[str, Any]]
        defending_direction : str

        Returns
        -------
        movement_records : List[DefenderMovementRecord]
        second_defender_summary : Dict[str, Any]
        coordination_features : EpisodeDefenderFeatures
        """
        first_def_id = first_defender_info["player_id"]
        fps = self.config.fps

        # Window with 5 pre-frames to evaluate pre-existing movement
        pre_start_frame = max(0, episode_start_frame - 5)
        all_frames = [
            tracking_index[f]
            for f in range(pre_start_frame, episode_end_frame + 1)
            if f in tracking_index
        ]
        episode_frames = [f for f in all_frames if f["frame"] >= episode_start_frame]

        # Extract ball positions
        ball_positions: Dict[int, Tuple[float, float]] = {}
        for f in all_frames:
            f_num = f["frame"]
            b = f.get("ball_data", {})
            if b and b.get("x") is not None and b.get("y") is not None:
                ball_positions[f_num] = (float(b["x"]), float(b["y"]))

        # Identify all active outfield defenders present during the episode
        active_defenders: Set[int] = set()
        for f in episode_frames:
            for p in f.get("player_data", []):
                pid = p.get("player_id")
                p_meta = self.player_registry.get(pid, {})
                if p_meta.get("team_id") == defending_team_id and not p_meta.get("is_goalkeeper", False):
                    active_defenders.add(pid)

        # Collect trajectory for each defender from pre_start_frame to episode_end_frame
        defender_trajectories_full: Dict[int, Dict[str, Any]] = {}
        defender_trajectories_episode: Dict[int, Dict[str, Any]] = {}

        for def_id in active_defenders:
            full_f, full_x, full_y = [], [], []
            ep_f, ep_x, ep_y = [], [], []

            for f in all_frames:
                f_num = f["frame"]
                for p in f.get("player_data", []):
                    if p.get("player_id") == def_id:
                        full_f.append(f_num)
                        full_x.append(float(p["x"]))
                        full_y.append(float(p["y"]))
                        if f_num >= episode_start_frame:
                            ep_f.append(f_num)
                            ep_x.append(float(p["x"]))
                            ep_y.append(float(p["y"]))
                        break

            if len(ep_f) >= 2:
                defender_trajectories_full[def_id] = {"frames": full_f, "xs": full_x, "ys": full_y}
                defender_trajectories_episode[def_id] = {"frames": ep_f, "xs": ep_x, "ys": ep_y}

        # Analyze pre-start movement and segment trajectories
        defender_pre_moving: Dict[int, bool] = {}
        defender_segments: Dict[int, List[Dict[str, Any]]] = {}

        for def_id, traj_full in defender_trajectories_full.items():
            traj_ep = defender_trajectories_episode[def_id]
            full_xs = np.array(traj_full["xs"])
            full_ys = np.array(traj_full["ys"])
            full_speeds, _ = calculate_trajectory_speed_and_acceleration(full_xs, full_ys, fps=fps)

            # Find index corresponding to episode_start_frame
            start_indices = [idx for idx, f in enumerate(traj_full["frames"]) if f == episode_start_frame]
            start_idx = start_indices[0] if start_indices else len(traj_full["frames"]) - 1

            # Check pre-start speed (average speed in 3 frames before episode start)
            pre_slice = full_speeds[max(0, start_idx - 3) : start_idx]
            was_pre_moving = bool(len(pre_slice) > 0 and np.mean(pre_slice) >= self.config.movement_speed_threshold_mps)
            defender_pre_moving[def_id] = was_pre_moving

            # Segment post-start movement within the episode window
            segs = detect_movement_segments(
                frames=traj_ep["frames"],
                xs=traj_ep["xs"],
                ys=traj_ep["ys"],
                speed_threshold_mps=self.config.movement_speed_threshold_mps,
                min_consecutive_frames=self.config.movement_onset_window_frames,
                fps=fps,
            )
            defender_segments[def_id] = segs

        # Calculate each defender's spatial proximity to First Defender at Episode Start
        first_def_pos_start: Optional[Tuple[float, float]] = None
        if first_def_id in defender_trajectories_episode:
            first_def_pos_start = (
                defender_trajectories_episode[first_def_id]["xs"][0],
                defender_trajectories_episode[first_def_id]["ys"][0]
            )

        defender_dist_to_first: Dict[int, float] = {}
        defender_min_dist_to_first: Dict[int, float] = {}
        defender_closed_to_first: Dict[int, float] = {}

        for def_id, traj_ep in defender_trajectories_episode.items():
            if first_def_pos_start is not None and def_id != first_def_id:
                d_init = calculate_euclidean_distance(
                    traj_ep["xs"][0], traj_ep["ys"][0],
                    first_def_pos_start[0], first_def_pos_start[1]
                )
                defender_dist_to_first[def_id] = d_init

                # Track minimum distance achieved to First Defender during the episode
                if first_def_id in defender_trajectories_episode:
                    f_xs = defender_trajectories_episode[first_def_id]["xs"]
                    f_ys = defender_trajectories_episode[first_def_id]["ys"]
                    p_xs = traj_ep["xs"]
                    p_ys = traj_ep["ys"]
                    n_pts = min(len(f_xs), len(p_xs))
                    d_min = min(calculate_euclidean_distance(p_xs[i], p_ys[i], f_xs[i], f_ys[i]) for i in range(n_pts))
                    defender_min_dist_to_first[def_id] = d_min
                    defender_closed_to_first[def_id] = d_init - d_min
                else:
                    defender_min_dist_to_first[def_id] = d_init
                    defender_closed_to_first[def_id] = 0.0

        # Identify Second Defender Candidates
        # Group 1: Defenders with genuine new movement onsets strictly after Episode Start
        new_onset_candidates: List[Dict[str, Any]] = []
        continuation_candidates: List[Dict[str, Any]] = []

        max_dist_cover = self.config.second_defender_max_distance_to_first_m

        for def_id, segs in defender_segments.items():
            if def_id == first_def_id:
                continue

            dist_to_first = defender_dist_to_first.get(def_id, 999.0)
            d_min_to_first = defender_min_dist_to_first.get(def_id, dist_to_first)
            closed_to_first = defender_closed_to_first.get(def_id, 0.0)

            for s in segs:
                onset_f = s["onset_frame"]
                cand_data = {
                    "player_id": def_id,
                    "onset_frame": onset_f,
                    "time_to_onset_sec": 0.0 if onset_f == episode_start_frame else (onset_f - episode_start_frame) / fps,
                    "dist_to_first": dist_to_first,
                    "d_min_to_first": d_min_to_first,
                    "closed_to_first": closed_to_first,
                    "segment": s,
                }
                # If segment begins at the start frame and defender was pre-moving, it is a continuation
                if onset_f == episode_start_frame and defender_pre_moving.get(def_id, False):
                    cand_data["is_continuation"] = True
                    continuation_candidates.append(cand_data)
                elif onset_f > episode_start_frame or (onset_f == episode_start_frame and not defender_pre_moving.get(def_id, False)):
                    # Genuine new onset
                    cand_data["is_continuation"] = False
                    new_onset_candidates.append(cand_data)
                    break  # Take earliest post-start onset for this defender

        # Strict spatial relevance: Second Defender MUST be within tactical cover proximity at start
        # (<= second_defender_max_distance_to_first_m, default 18.0m).
        # In football tactics (Pressure-Cover-Balance), players beyond 18m at start provide weak-side balance
        # or central depth, NOT tactical cover for this specific engagement.
        spatially_relevant_new = [
            c for c in new_onset_candidates
            if c["dist_to_first"] <= max_dist_cover
        ]
        spatially_relevant_cont = [
            c for c in continuation_candidates
            if c["dist_to_first"] <= max_dist_cover
        ]

        # Active covering continuations: defenders within proximity already moving at start who actively
        # close down towards First Defender (closed >= 1.5m) or maintain close cover (<= 8.0m)
        active_covering_continuations = [
            c for c in spatially_relevant_cont
            if c["d_min_to_first"] <= 8.0 or c["closed_to_first"] >= 1.5
        ]

        # Combine new onsets with active covering movements at start
        candidate_pool = spatially_relevant_new + active_covering_continuations
        if not candidate_pool:
            candidate_pool = spatially_relevant_cont

        # Select Second Defender and simultaneous responders
        second_def_id: Optional[int] = None
        second_def_name: Optional[str] = None
        second_def_onset_frame: Optional[int] = None
        has_simultaneous = False
        simultaneous_ids: List[int] = []
        reaction_time_sec: Optional[float] = None

        if candidate_pool:
            # Sort by onset frame first, and break spatial ties by closest achieved distance to First Defender
            candidate_pool.sort(key=lambda c: (c["onset_frame"], c["d_min_to_first"], -c["closed_to_first"]))
            earliest_onset = candidate_pool[0]["onset_frame"]

            # Filter candidates within simultaneous tolerance
            sim_candidates = [
                c for c in candidate_pool
                if (c["onset_frame"] - earliest_onset) <= self.config.simultaneous_tolerance_frames
            ]

            # Break tie among simultaneous responders by selecting the defender with closest covering proximity
            sim_candidates.sort(key=lambda c: (c["d_min_to_first"], -c["closed_to_first"]))
            primary = sim_candidates[0]
            second_def_id = primary["player_id"]
            second_def_name = self.player_registry.get(second_def_id, {}).get("short_name", f"Player {second_def_id}")
            second_def_onset_frame = primary["onset_frame"]
            reaction_time_sec = primary["time_to_onset_sec"]

            simultaneous_ids = list(dict.fromkeys([c["player_id"] for c in sim_candidates]))
            has_simultaneous = len(simultaneous_ids) > 1

        second_defender_summary = {
            "second_defender_id": second_def_id,
            "second_defender_name": second_def_name,
            "second_defender_onset_frame": second_def_onset_frame,
            "has_simultaneous_second_responders": has_simultaneous,
            "simultaneous_second_defender_ids": ",".join(str(i) for i in simultaneous_ids),
            "reaction_time_sec": reaction_time_sec,
        }

        # Build movement records for each defender
        movement_records: List[DefenderMovementRecord] = []
        frame_timestamps = {f["frame"]: f.get("timestamp", "") for f in all_frames}

        for def_id, traj_ep in defender_trajectories_episode.items():
            p_name = self.player_registry.get(def_id, {}).get("short_name", f"Player {def_id}")

            # Role classification
            if def_id == first_def_id:
                role = "FIRST_DEFENDER"
            elif def_id == second_def_id:
                role = "SECOND_DEFENDER"
            elif def_id in simultaneous_ids and has_simultaneous:
                role = "SECOND_DEFENDER"
            else:
                role = "SUPPORTING_DEFENDER"

            segs = defender_segments.get(def_id, [])
            if not segs:
                # Still record overall trajectory for stationary/drifting defenders
                xs_arr = np.array(traj_ep["xs"])
                ys_arr = np.array(traj_ep["ys"])
                speeds, _ = calculate_trajectory_speed_and_acceleration(xs_arr, ys_arr, fps=fps)
                disp_x = float(xs_arr[-1] - xs_arr[0])
                disp_y = float(ys_arr[-1] - ys_arr[0])
                tot_dist = float(np.sum(np.hypot(np.diff(xs_arr), np.diff(ys_arr)))) if len(xs_arr) > 1 else 0.0

                b_start = ball_positions.get(episode_start_frame, (0.0, 0.0))
                b_end = ball_positions.get(episode_end_frame, (0.0, 0.0))
                d_start = calculate_euclidean_distance(xs_arr[0], ys_arr[0], b_start[0], b_start[1])
                d_end = calculate_euclidean_distance(xs_arr[-1], ys_arr[-1], b_end[0], b_end[1])

                movement_records.append(DefenderMovementRecord(
                    match_id=match_id,
                    episode_id=episode_id,
                    player_id=def_id,
                    player_name=p_name,
                    team_id=defending_team_id,
                    defender_role=role,
                    is_simultaneous_responder=bool(def_id in simultaneous_ids and has_simultaneous),
                    movement_onset_frame=episode_start_frame,
                    movement_onset_timestamp=frame_timestamps.get(episode_start_frame, ""),
                    movement_end_frame=episode_end_frame,
                    movement_end_timestamp=frame_timestamps.get(episode_end_frame, ""),
                    movement_duration_seconds=(episode_end_frame - episode_start_frame + 1) / fps,
                    time_to_onset_from_episode_start_sec=0.0,
                    is_pre_existing_continuation=defender_pre_moving.get(def_id, False),
                    start_x=float(xs_arr[0]),
                    start_y=float(ys_arr[0]),
                    end_x=float(xs_arr[-1]),
                    end_y=float(ys_arr[-1]),
                    displacement_x=disp_x,
                    displacement_y=disp_y,
                    total_distance=tot_dist,
                    mean_speed=float(np.mean(speeds)),
                    max_speed=float(np.max(speeds)),
                    movement_direction_deg=calculate_movement_direction(disp_x, disp_y),
                    initial_distance_to_ball=d_start,
                    final_distance_to_ball=d_end,
                    delta_distance_to_ball=d_start - d_end,
                    is_mdm_qualifying=(def_id == first_def_id),
                ))
            else:
                for s in segs:
                    b_start = ball_positions.get(s["onset_frame"], (0.0, 0.0))
                    b_end = ball_positions.get(s["end_frame"], (0.0, 0.0))
                    d_start = calculate_euclidean_distance(s["start_x"], s["start_y"], b_start[0], b_start[1])
                    d_end = calculate_euclidean_distance(s["end_x"], s["end_y"], b_end[0], b_end[1])

                    is_cont = bool(s["onset_frame"] == episode_start_frame and defender_pre_moving.get(def_id, False))

                    movement_records.append(DefenderMovementRecord(
                        match_id=match_id,
                        episode_id=episode_id,
                        player_id=def_id,
                        player_name=p_name,
                        team_id=defending_team_id,
                        defender_role=role,
                        is_simultaneous_responder=bool(def_id in simultaneous_ids and has_simultaneous),
                        movement_onset_frame=s["onset_frame"],
                        movement_onset_timestamp=frame_timestamps.get(s["onset_frame"], ""),
                        movement_end_frame=s["end_frame"],
                        movement_end_timestamp=frame_timestamps.get(s["end_frame"], ""),
                        movement_duration_seconds=s["duration_seconds"],
                        time_to_onset_from_episode_start_sec=max(0.0, (s["onset_frame"] - episode_start_frame) / fps),
                        is_pre_existing_continuation=is_cont,
                        start_x=s["start_x"],
                        start_y=s["start_y"],
                        end_x=s["end_x"],
                        end_y=s["end_y"],
                        displacement_x=s["displacement_x"],
                        displacement_y=s["displacement_y"],
                        total_distance=s["total_distance"],
                        mean_speed=s["mean_speed"],
                        max_speed=s["max_speed"],
                        movement_direction_deg=s["direction_deg"],
                        initial_distance_to_ball=d_start,
                        final_distance_to_ball=d_end,
                        delta_distance_to_ball=d_start - d_end,
                        is_mdm_qualifying=(def_id == first_def_id and s["onset_frame"] == episode_start_frame),
                    ))

        # Coordination Features
        f_traj = defender_trajectories_episode.get(first_def_id)
        if f_traj:
            f_xs = np.array(f_traj["xs"])
            f_ys = np.array(f_traj["ys"])
            f_speeds, _ = calculate_trajectory_speed_and_acceleration(f_xs, f_ys, fps=fps)
            f_tot_dist = float(np.sum(np.hypot(np.diff(f_xs), np.diff(f_ys)))) if len(f_xs) > 1 else 0.0
            f_mean_spd = float(np.mean(f_speeds))
            f_disp_x = float(f_xs[-1] - f_xs[0])
            f_disp_y = float(f_ys[-1] - f_ys[0])
            b_start = ball_positions.get(episode_start_frame, (0.0, 0.0))
            f_app_vec = (b_start[0] - f_xs[0], b_start[1] - f_ys[0])
            f_angle_to_ball = vector_alignment((f_disp_x, f_disp_y), f_app_vec)
        else:
            f_tot_dist, f_mean_spd, f_angle_to_ball = 0.0, 0.0, None

        dist_12_start: Optional[float] = None
        dist_12_end: Optional[float] = None
        dist_12_change: Optional[float] = None
        alignment_12: Optional[float] = None

        if second_def_id and f_traj and second_def_id in defender_trajectories_episode:
            s_traj = defender_trajectories_episode[second_def_id]
            s_xs = np.array(s_traj["xs"])
            s_ys = np.array(s_traj["ys"])

            dist_12_start = calculate_euclidean_distance(f_xs[0], f_ys[0], s_xs[0], s_ys[0])
            dist_12_end = calculate_euclidean_distance(f_xs[-1], f_ys[-1], s_xs[-1], s_ys[-1])
            dist_12_change = dist_12_end - dist_12_start

            s_disp_x = float(s_xs[-1] - s_xs[0])
            s_disp_y = float(s_ys[-1] - s_ys[0])
            alignment_12 = vector_alignment((f_disp_x, f_disp_y), (s_disp_x, s_disp_y))

        start_def_pos = [
            (traj["xs"][0], traj["ys"][0])
            for traj in defender_trajectories_episode.values()
        ]
        end_def_pos = [
            (traj["xs"][-1], traj["ys"][-1])
            for traj in defender_trajectories_episode.values()
        ]

        comp_start = calculate_team_compactness(start_def_pos)
        comp_end = calculate_team_compactness(end_def_pos)

        def_line_start = calculate_defensive_line_x(start_def_pos, defending_direction)
        def_line_end = calculate_defensive_line_x(end_def_pos, defending_direction)

        coordination_features = EpisodeDefenderFeatures(
            match_id=match_id,
            episode_id=episode_id,
            second_defender_reaction_time_sec=reaction_time_sec,
            first_defender_total_distance=f_tot_dist,
            first_defender_mean_speed=f_mean_spd,
            first_defender_approach_vector_angle_to_ball=f_angle_to_ball,
            inter_defender_dist_start_first_second=dist_12_start,
            inter_defender_dist_end_first_second=dist_12_end,
            inter_defender_dist_change_first_second=dist_12_change,
            defensive_compactness_start=comp_start["spread_radius"],
            defensive_compactness_end=comp_end["spread_radius"],
            compactness_change=comp_end["spread_radius"] - comp_start["spread_radius"],
            defensive_line_x_start=def_line_start,
            defensive_line_x_end=def_line_end,
            n_simultaneous_responders=len(simultaneous_ids),
            simultaneous_response_tolerance_frames=self.config.simultaneous_tolerance_frames,
            second_defender_direction_alignment_to_first=alignment_12,
        )

        return movement_records, second_defender_summary, coordination_features
