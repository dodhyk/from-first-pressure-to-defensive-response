"""Data schemas, dataclasses, and output record definitions for the pipeline.

Defines typed representations for episodes, defender movements, episode-level features,
and validation audits to ensure data contracts and clean CSV serialization.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class EpisodeRecord:
    """Episode-level analytical record (1 row per defensive episode)."""
    match_id: int
    episode_id: str
    period: int
    attacking_team_id: int
    defending_team_id: int
    attacking_trigger_type: str
    attacking_trigger_frame: int
    attacking_trigger_timestamp: str
    ball_carrier_id: Optional[int]
    ball_carrier_name: Optional[str]
    episode_start_frame: int
    episode_start_timestamp: str
    episode_end_frame: int
    episode_end_timestamp: str
    duration_frames: int
    duration_seconds: float
    first_defender_id: int
    first_defender_name: str
    first_defender_onset_frame: int
    second_defender_id: Optional[int]
    second_defender_name: Optional[str]
    second_defender_onset_frame: Optional[int]
    has_simultaneous_second_responders: bool
    simultaneous_second_defender_ids: str
    supporting_defender_ids: str
    n_defenders_involved: int
    main_outcome: str  # PROGRESSION, NO_PROGRESSION, TURNOVER, UNRESOLVED
    detailed_outcome: str
    epv_against_start: Optional[float]
    epv_against_end: Optional[float]
    defensive_value: Optional[float]  # DV = epv_against_start - epv_against_end
    epv_source: str
    epv_method: str
    epv_missing_status: str
    data_quality_flags: str
    boundary_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DefenderMovementRecord:
    """Individual defender movement segment record (1 row per defender movement)."""
    match_id: int
    episode_id: str
    player_id: int
    player_name: str
    team_id: int
    defender_role: str  # FIRST_DEFENDER, SECOND_DEFENDER, SUPPORTING_DEFENDER
    is_simultaneous_responder: bool
    movement_onset_frame: int
    movement_onset_timestamp: str
    movement_end_frame: int
    movement_end_timestamp: str
    movement_duration_seconds: float
    time_to_onset_from_episode_start_sec: float
    is_pre_existing_continuation: bool
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    displacement_x: float
    displacement_y: float
    total_distance: float
    mean_speed: float
    max_speed: float
    movement_direction_deg: float
    initial_distance_to_ball: float
    final_distance_to_ball: float
    delta_distance_to_ball: float
    is_mdm_qualifying: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeDefenderFeatures:
    """Episode-level defensive coordination features (1 row per episode)."""
    match_id: int
    episode_id: str
    second_defender_reaction_time_sec: Optional[float]
    first_defender_total_distance: float
    first_defender_mean_speed: float
    first_defender_approach_vector_angle_to_ball: Optional[float]
    inter_defender_dist_start_first_second: Optional[float]
    inter_defender_dist_end_first_second: Optional[float]
    inter_defender_dist_change_first_second: Optional[float]
    defensive_compactness_start: float
    defensive_compactness_end: float
    compactness_change: float
    defensive_line_x_start: float
    defensive_line_x_end: float
    n_simultaneous_responders: int
    simultaneous_response_tolerance_frames: int
    second_defender_direction_alignment_to_first: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeValidationRecord:
    """Audit and manual-review record for validating episode detections."""
    match_id: int
    episode_id: str
    validation_status: str  # VALIDATED, BORDERLINE_MDM, SIMULTANEOUS_TIE, etc.
    validation_tier: str    # HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, REQUIRES_MANUAL_REVIEW
    review_notes: str
    has_gif: bool
    gif_path: str
    has_trajectory_plot: bool
    plot_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
