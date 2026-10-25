"""Movement feature extraction and spatial geometry for football tracking data.

Calculates velocities, accelerations, distances, angles, defensive compactness,
and movement onsets from 10 FPS extrapolated tracking.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def calculate_euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two 2D points in meters."""
    return float(np.hypot(x2 - x1, y2 - y1))


def calculate_trajectory_speed_and_acceleration(
    xs: np.ndarray,
    ys: np.ndarray,
    fps: float = 10.0,
    smooth: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate instantaneous speed (m/s) and acceleration (m/s^2) for a trajectory.

    Parameters
    ----------
    xs : np.ndarray
        Array of x positions in meters.
    ys : np.ndarray
        Array of y positions in meters.
    fps : float
        Tracking sampling rate in frames per second (default 10.0).
    smooth : bool
        Whether to apply 3-frame moving average smoothing to reduce tracking jitter.

    Returns
    -------
    speeds : np.ndarray
        Speed at each frame in m/s.
    accelerations : np.ndarray
        Acceleration at each frame in m/s^2.
    """
    n = len(xs)
    if n < 2:
        return np.zeros(n), np.zeros(n)

    dt = 1.0 / fps

    # Finite difference displacement
    dx = np.gradient(xs, dt)
    dy = np.gradient(ys, dt)
    raw_speeds = np.hypot(dx, dy)

    if smooth and n >= 3:
        # 3-frame rolling window smoothing preserving length
        kernel = np.array([0.25, 0.5, 0.25])
        padded = np.pad(raw_speeds, (1, 1), mode="edge")
        speeds = np.convolve(padded, kernel, mode="valid")
    else:
        speeds = raw_speeds

    accelerations = np.gradient(speeds, dt)
    return speeds, accelerations


def calculate_movement_direction(dx: float, dy: float) -> float:
    """Calculate movement direction angle in degrees [-180, 180] where 0 deg is +x."""
    return float(np.degrees(np.arctan2(dy, dx)))


def detect_movement_segments(
    frames: List[int],
    xs: List[float],
    ys: List[float],
    speed_threshold_mps: float = 1.2,
    min_consecutive_frames: int = 3,
    fps: float = 10.0,
) -> List[Dict[str, Any]]:
    """Segment a continuous player trajectory into active movement bouts.

    Parameters
    ----------
    frames : List[int]
        Frame numbers corresponding to the trajectory.
    xs, ys : List[float]
        Player x and y coordinates in meters.
    speed_threshold_mps : float
        Speed threshold (m/s) above which active movement occurs.
    min_consecutive_frames : int
        Minimum duration (frames) to register an onset and avoid tracking flicker.
    fps : float
        Frame rate.

    Returns
    -------
    segments : List[Dict[str, Any]]
        List of movement segment dicts with onset, end, displacement, speed, etc.
    """
    if len(frames) < 2:
        return []

    xs_arr = np.array(xs, dtype=float)
    ys_arr = np.array(ys, dtype=float)
    speeds, accels = calculate_trajectory_speed_and_acceleration(xs_arr, ys_arr, fps=fps)

    is_moving = speeds >= speed_threshold_mps
    segments = []
    in_segment = False
    seg_start_idx = 0

    for i in range(len(is_moving)):
        if is_moving[i] and not in_segment:
            # Check lookahead to ensure persistence
            lookahead = is_moving[i : i + min_consecutive_frames]
            if len(lookahead) >= min_consecutive_frames and np.all(lookahead):
                in_segment = True
                seg_start_idx = i
        elif not is_moving[i] and in_segment:
            # End of segment
            seg_end_idx = i - 1
            if (seg_end_idx - seg_start_idx + 1) >= min_consecutive_frames:
                sub_xs = xs_arr[seg_start_idx : seg_end_idx + 1]
                sub_ys = ys_arr[seg_start_idx : seg_end_idx + 1]
                sub_speeds = speeds[seg_start_idx : seg_end_idx + 1]

                disp_x = float(sub_xs[-1] - sub_xs[0])
                disp_y = float(sub_ys[-1] - sub_ys[0])
                step_dists = np.hypot(np.diff(sub_xs), np.diff(sub_ys))
                tot_dist = float(np.sum(step_dists))

                segments.append({
                    "start_idx": seg_start_idx,
                    "end_idx": seg_end_idx,
                    "onset_frame": frames[seg_start_idx],
                    "end_frame": frames[seg_end_idx],
                    "duration_frames": seg_end_idx - seg_start_idx + 1,
                    "duration_seconds": (seg_end_idx - seg_start_idx + 1) / fps,
                    "start_x": float(sub_xs[0]),
                    "start_y": float(sub_ys[0]),
                    "end_x": float(sub_xs[-1]),
                    "end_y": float(sub_ys[-1]),
                    "displacement_x": disp_x,
                    "displacement_y": disp_y,
                    "total_distance": tot_dist,
                    "mean_speed": float(np.mean(sub_speeds)),
                    "max_speed": float(np.max(sub_speeds)),
                    "direction_deg": calculate_movement_direction(disp_x, disp_y),
                })
            in_segment = False

    # Check open segment at the end of window
    if in_segment:
        seg_end_idx = len(is_moving) - 1
        if (seg_end_idx - seg_start_idx + 1) >= min_consecutive_frames:
            sub_xs = xs_arr[seg_start_idx : seg_end_idx + 1]
            sub_ys = ys_arr[seg_start_idx : seg_end_idx + 1]
            sub_speeds = speeds[seg_start_idx : seg_end_idx + 1]

            disp_x = float(sub_xs[-1] - sub_xs[0])
            disp_y = float(sub_ys[-1] - sub_ys[0])
            step_dists = np.hypot(np.diff(sub_xs), np.diff(sub_ys))
            tot_dist = float(np.sum(step_dists))

            segments.append({
                "start_idx": seg_start_idx,
                "end_idx": seg_end_idx,
                "onset_frame": frames[seg_start_idx],
                "end_frame": frames[seg_end_idx],
                "duration_frames": seg_end_idx - seg_start_idx + 1,
                "duration_seconds": (seg_end_idx - seg_start_idx + 1) / fps,
                "start_x": float(sub_xs[0]),
                "start_y": float(sub_ys[0]),
                "end_x": float(sub_xs[-1]),
                "end_y": float(sub_ys[-1]),
                "displacement_x": disp_x,
                "displacement_y": disp_y,
                "total_distance": tot_dist,
                "mean_speed": float(np.mean(sub_speeds)),
                "max_speed": float(np.max(sub_speeds)),
                "direction_deg": calculate_movement_direction(disp_x, disp_y),
            })

    return segments


def calculate_team_compactness(
    player_positions: List[Tuple[float, float]]
) -> Dict[str, float]:
    """Calculate defensive unit spatial dispersion and compactness in meters.

    Parameters
    ----------
    player_positions : List[Tuple[float, float]]
        List of (x, y) coordinates of outfield defending players.

    Returns
    -------
    metrics : Dict[str, float]
        std_x, std_y, spread_radius (mean distance from centroid), bounding_area
    """
    if len(player_positions) < 2:
        return {"std_x": 0.0, "std_y": 0.0, "spread_radius": 0.0, "bounding_area": 0.0}

    arr = np.array(player_positions)
    xs = arr[:, 0]
    ys = arr[:, 1]

    cx, cy = np.mean(xs), np.mean(ys)
    radii = np.hypot(xs - cx, ys - cy)
    spread_radius = float(np.mean(radii))
    std_x = float(np.std(xs))
    std_y = float(np.std(ys))
    bounding_area = float((np.max(xs) - np.min(xs)) * (np.max(ys) - np.min(ys)))

    return {
        "std_x": std_x,
        "std_y": std_y,
        "spread_radius": spread_radius,
        "bounding_area": bounding_area,
    }


def calculate_defensive_line_x(
    defender_positions: List[Tuple[float, float]],
    defending_direction: str = "left_to_right"
) -> float:
    """Calculate the position of the last defensive line along the longitudinal axis (x).

    Parameters
    ----------
    defender_positions : List[Tuple[float, float]]
        Outfield defender (x, y) coordinates.
    defending_direction : str
        Direction the defending team defends toward.
        If defending left-hand goal (-52), deepest defenders have smallest x.
        If defending right-hand goal (+52), deepest defenders have largest x.
    """
    if not defender_positions:
        return 0.0

    xs = [p[0] for p in defender_positions]
    if defending_direction == "left_to_right":
        # Defending team defends x = -52 (left goal)
        deepest = sorted(xs)[:3]
        return float(np.mean(deepest))
    else:
        # Defending team defends x = +52 (right goal)
        deepest = sorted(xs, reverse=True)[:3]
        return float(np.mean(deepest))


def point_to_segment_distance(
    px: float, py: float,
    x1: float, y1: float,
    x2: float, y2: float
) -> float:
    """Calculate the shortest distance from point (px, py) to line segment (x1, y1)-(x2, y2).

    Used for measuring passing lane interception / lane closure geometry.
    """
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq < 1e-6:
        return calculate_euclidean_distance(px, py, x1, y1)

    # Project point onto line segment: t in [0, 1]
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return calculate_euclidean_distance(px, py, proj_x, proj_y)


def is_in_defending_half(x: float, attacking_direction: str) -> bool:
    """Check if an x-coordinate is inside the defending team's own half (wilayah sendiri).

    SkillCorner standard coordinate system: center circle is x = 0, y = 0.
    Pitch bounds are x in [-52, +52].

    If attacking team attacks left_to_right (+x toward opponent goal at +52),
    defending team defends the goal at +52, so the defending team's own half is x >= 0.

    If attacking team attacks right_to_left (-x toward opponent goal at -52),
    defending team defends the goal at -52, so the defending team's own half is x <= 0.
    """
    if attacking_direction == "left_to_right":
        return x >= 0.0
    else:
        return x <= 0.0


def vector_alignment(v1: Tuple[float, float], v2: Tuple[float, float]) -> Optional[float]:
    """Compute cosine similarity between two 2D movement vectors [-1, 1]."""
    norm1 = np.hypot(v1[0], v1[1])
    norm2 = np.hypot(v2[0], v2[1])
    if norm1 < 1e-4 or norm2 < 1e-4:
        return None
    cos_sim = (v1[0] * v2[0] + v1[1] * v2[1]) / (norm1 * norm2)
    return float(np.clip(cos_sim, -1.0, 1.0))
