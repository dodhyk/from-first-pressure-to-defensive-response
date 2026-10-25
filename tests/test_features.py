"""Unit tests for spatial geometry, speed calculations, and movement features."""

import numpy as np
import pytest

from src.features import (
    calculate_defensive_line_x,
    calculate_euclidean_distance,
    calculate_movement_direction,
    calculate_team_compactness,
    calculate_trajectory_speed_and_acceleration,
    detect_movement_segments,
    is_in_defending_half,
    point_to_segment_distance,
    vector_alignment,
)


def test_euclidean_distance():
    assert calculate_euclidean_distance(0.0, 0.0, 3.0, 4.0) == pytest.approx(5.0)
    assert calculate_euclidean_distance(-10.0, 5.0, -10.0, 5.0) == 0.0


def test_speed_and_acceleration():
    # Linear movement at 5 m/s (0.5m displacement per 0.1s frame at 10 FPS)
    xs = np.arange(0.0, 10.0, 0.5)  # 20 frames
    ys = np.zeros_like(xs)

    speeds, accels = calculate_trajectory_speed_and_acceleration(xs, ys, fps=10.0, smooth=False)
    # Check middle points away from gradient boundary
    assert speeds[5] == pytest.approx(5.0, abs=0.1)
    assert accels[5] == pytest.approx(0.0, abs=0.1)


def test_movement_direction():
    # +x direction (0 deg)
    assert calculate_movement_direction(5.0, 0.0) == pytest.approx(0.0)
    # +y direction (90 deg)
    assert calculate_movement_direction(0.0, 5.0) == pytest.approx(90.0)
    # -x direction (180 deg)
    assert abs(calculate_movement_direction(-5.0, 0.0)) == pytest.approx(180.0)


def test_detect_movement_segments():
    # 5 frames stationary (0.0 m/s), 5 frames moving at 3.0 m/s, 5 frames stationary
    fps = 10.0
    frames = list(range(100, 115))
    xs = [0.0]*5 + [0.3 * i for i in range(1, 6)] + [1.5]*5
    ys = [0.0]*15

    segs = detect_movement_segments(frames, xs, ys, speed_threshold_mps=1.2, min_consecutive_frames=3, fps=fps)
    assert len(segs) == 1
    seg = segs[0]
    assert seg["onset_frame"] >= 104
    assert seg["mean_speed"] >= 1.2
    assert seg["total_distance"] > 1.0


def test_team_compactness():
    positions = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0)]
    compact = calculate_team_compactness(positions)
    assert compact["bounding_area"] == pytest.approx(100.0)
    assert compact["spread_radius"] > 0.0


def test_defensive_line_x():
    # Defending left goal (-52) -> smallest x is deepest
    positions = [(-30.0, 0.0), (-35.0, 5.0), (-32.0, -5.0), (-10.0, 0.0)]
    line_x = calculate_defensive_line_x(positions, defending_direction="left_to_right")
    # Top 3 deepest: -35, -32, -30 -> mean = -32.33
    assert line_x == pytest.approx(-32.333, abs=0.1)


def test_point_to_segment_distance():
    # Point (5, 5) to horizontal line segment from (0, 0) to (10, 0)
    dist = point_to_segment_distance(5.0, 5.0, 0.0, 0.0, 10.0, 0.0)
    assert dist == pytest.approx(5.0)


def test_vector_alignment():
    # Parallel vectors -> 1.0
    assert vector_alignment((1.0, 0.0), (3.0, 0.0)) == pytest.approx(1.0)
    # Orthogonal vectors -> 0.0
    assert vector_alignment((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    # Opposite vectors -> -1.0
    assert vector_alignment((1.0, 0.0), (-2.0, 0.0)) == pytest.approx(-1.0)


def test_is_in_defending_half():
    # When attacking team attacks left_to_right (+x towards +52):
    # Defending team defends goal at +52, so defending team's half is x >= 0
    assert is_in_defending_half(10.0, "left_to_right") is True
    assert is_in_defending_half(0.0, "left_to_right") is True
    assert is_in_defending_half(-5.0, "left_to_right") is False

    # When attacking team attacks right_to_left (-x towards -52):
    # Defending team defends goal at -52, so defending team's half is x <= 0
    assert is_in_defending_half(-15.0, "right_to_left") is True
    assert is_in_defending_half(0.0, "right_to_left") is True
    assert is_in_defending_half(8.0, "right_to_left") is False

