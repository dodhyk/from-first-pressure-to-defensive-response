"""Unit tests for episode tracking, post-start movement, and simultaneous responders."""

from src.config import PipelineConfig
from src.episode_tracker import EpisodeTracker


def test_stable_episode_id_formatting():
    match_id = 1886347
    idx = 42
    ep_id = f"{match_id}_EP_{idx:06d}"
    assert ep_id == "1886347_EP_000042"


def test_simultaneous_movement_detection():
    config = PipelineConfig(simultaneous_tolerance_frames=2)
    players = {
        1: {"id": 1, "short_name": "First Def", "team_id": 10, "is_goalkeeper": False},
        2: {"id": 2, "short_name": "Second Def A", "team_id": 10, "is_goalkeeper": False},
        3: {"id": 3, "short_name": "Second Def B", "team_id": 10, "is_goalkeeper": False},
    }
    tracker = EpisodeTracker(config, players)

    # Frame 10 to 20
    # Def 1 is First Defender (onset at 10)
    # Def 2 starts at frame 12 (0.2s after)
    # Def 3 starts at frame 13 (within 2 frames of 12) -> Simultaneous!
    tracking_index = {}
    for f in range(5, 25):
        tracking_index[f] = {
            "frame": f,
            "timestamp": f"00:00:{f/10:04.1f}",
            "ball_data": {"x": 0.0, "y": 0.0},
            "player_data": [
                # Def 1 moving from frame 10
                {"player_id": 1, "x": 10.0 + (f-10)*0.5 if f >= 10 else 10.0, "y": 0.0},
                # Def 2 stationary until 12, then moves
                {"player_id": 2, "x": 15.0 + (f-12)*0.4 if f >= 12 else 15.0, "y": 5.0},
                # Def 3 stationary until 13, then moves
                {"player_id": 3, "x": 15.0 + (f-13)*0.4 if f >= 13 else 15.0, "y": -5.0},
            ]
        }

    first_info = {"player_id": 1, "player_name": "First Def", "onset_frame": 10}
    moves, summary, coord = tracker.track_defenders(
        episode_id="1886347_EP_000001",
        match_id=1886347,
        defending_team_id=10,
        first_defender_info=first_info,
        episode_start_frame=10,
        episode_end_frame=20,
        tracking_index=tracking_index,
    )

    assert summary["second_defender_id"] in [2, 3]
    # Check that simultaneous responder information is preserved
    assert summary["has_simultaneous_second_responders"] is True
    assert "2" in summary["simultaneous_second_defender_ids"]
    assert "3" in summary["simultaneous_second_defender_ids"]


def test_second_defender_distance_proximity_filtering():
    """Test that a defender farther than second_defender_max_distance_to_first_m is excluded."""
    config = PipelineConfig(second_defender_max_distance_to_first_m=15.0)
    players = {
        1: {"id": 1, "short_name": "First Def", "team_id": 10, "is_goalkeeper": False},
        2: {"id": 2, "short_name": "Far Defender", "team_id": 10, "is_goalkeeper": False},
        3: {"id": 3, "short_name": "Close Defender", "team_id": 10, "is_goalkeeper": False},
    }
    tracker = EpisodeTracker(config, players)

    # Def 1 is at (0, 0)
    # Def 2 is at (25, 0) -> distance = 25m (> 15m), moves earlier at frame 11
    # Def 3 is at (8, 0) -> distance = 8m (<= 15m), moves at frame 14
    tracking_index = {}
    for f in range(5, 25):
        tracking_index[f] = {
            "frame": f,
            "timestamp": f"00:00:{f/10:04.1f}",
            "ball_data": {"x": 0.0, "y": 0.0},
            "player_data": [
                {"player_id": 1, "x": 0.0 + (f - 10) * 0.5 if f >= 10 else 0.0, "y": 0.0},
                {"player_id": 2, "x": 25.0 + (f - 11) * 0.4 if f >= 11 else 25.0, "y": 0.0},
                {"player_id": 3, "x": 8.0 + (f - 14) * 0.4 if f >= 14 else 8.0, "y": 0.0},
            ],
        }

    first_info = {"player_id": 1, "player_name": "First Def", "onset_frame": 10}
    moves, summary, coord = tracker.track_defenders(
        episode_id="1886347_EP_000002",
        match_id=1886347,
        defending_team_id=10,
        first_defender_info=first_info,
        episode_start_frame=10,
        episode_end_frame=20,
        tracking_index=tracking_index,
    )

    # Far Defender (2) must be excluded despite moving earlier at frame 11
    # Close Defender (3) must be chosen as Second Defender
    assert summary["second_defender_id"] == 3
    assert summary["second_defender_name"] == "Close Defender"
    assert summary["second_defender_onset_frame"] == 14


def test_isolated_press_when_no_defender_within_proximity():
    """Test that second_defender_id is None when all teammates are > 15m away."""
    config = PipelineConfig(second_defender_max_distance_to_first_m=15.0)
    players = {
        1: {"id": 1, "short_name": "First Def", "team_id": 10, "is_goalkeeper": False},
        2: {"id": 2, "short_name": "Distant Def A", "team_id": 10, "is_goalkeeper": False},
        3: {"id": 3, "short_name": "Distant Def B", "team_id": 10, "is_goalkeeper": False},
    }
    tracker = EpisodeTracker(config, players)

    # Def 1 is at (0, 0)
    # Def 2 is at (22, 0) -> distance = 22m (> 15m)
    # Def 3 is at (0, 20) -> distance = 20m (> 15m)
    tracking_index = {}
    for f in range(5, 25):
        tracking_index[f] = {
            "frame": f,
            "timestamp": f"00:00:{f/10:04.1f}",
            "ball_data": {"x": 0.0, "y": 0.0},
            "player_data": [
                {"player_id": 1, "x": 0.0 + (f - 10) * 0.5 if f >= 10 else 0.0, "y": 0.0},
                {"player_id": 2, "x": 22.0 + (f - 11) * 0.4 if f >= 11 else 22.0, "y": 0.0},
                {"player_id": 3, "x": 0.0, "y": 20.0 + (f - 12) * 0.4 if f >= 12 else 20.0},
            ],
        }

    first_info = {"player_id": 1, "player_name": "First Def", "onset_frame": 10}
    moves, summary, coord = tracker.track_defenders(
        episode_id="1886347_EP_000003",
        match_id=1886347,
        defending_team_id=10,
        first_defender_info=first_info,
        episode_start_frame=10,
        episode_end_frame=20,
        tracking_index=tracking_index,
    )

    # Both defenders are > 15m away, so isolated press
    assert summary["second_defender_id"] is None
    assert summary["second_defender_name"] is None
    assert summary["second_defender_onset_frame"] is None
    assert summary["reaction_time_sec"] is None

