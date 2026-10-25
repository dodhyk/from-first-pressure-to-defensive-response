"""Configuration module for the Defensive Response research pipeline.

All thresholds, temporal parameters, and spatial tolerances are defined here
with explicit units, operational justifications, and sensitivity ranges.
"""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PipelineConfig:
    """Configuration parameters for episode detection and defensive movement analysis."""

    # Match identification
    match_id: int = 1886347

    # Directory layout
    data_dir: str = "data"
    output_dir: str = "outputs"
    force_download: bool = False

    # Pitch & Sampling parameters (SkillCorner standard: 10 FPS tracking, pitch length/width in meters)
    fps: float = 10.0  # Frames per second in extrapolated tracking (1 frame = 0.1s)
    pitch_length: float = 104.0  # Pitch length in meters (default fallback if missing in metadata)
    pitch_width: float = 68.0  # Pitch width in meters (default fallback if missing in metadata)

    # Attacking Trigger Operationalization
    # Trigger: Active offensive possession onset (player_possession or team phase start)
    min_trigger_duration_frames: int = 5  # 0.5s minimum possession length to establish attacking context
    only_defending_half: bool = True
    # Operational decision: defensive calculation strictly begins when the ball crosses the halfway line (x=0)
    # and enters the defending team's own half/territory (wilayah sendiri). Possessions that occur solely
    # in the opponent's half without crossing the halfway line are excluded.

    # Candidate First Defender & MDM (Meaningful Defensive Movement) Rules
    # Layer 1: Movement evidence
    mdm_speed_threshold_mps: float = 1.5
    # Unit: meters per second. Walking is typically 1.0-1.2 m/s; 1.5 m/s indicates purposeful jog/run.
    mdm_displacement_min_m: float = 0.6
    # Unit: meters. Minimum total movement displacement during MDM candidate window (0.5s = 5 frames).
    # A threshold of 0.6m in 0.5s (average speed 1.2 m/s) allows defenders jockeying or containing the ball carrier
    # with agile steps to qualify, avoiding exclusion of defenders in direct 1v1 engagement.

    # Layer 2 & 3: Defensive context & Spatial relevance
    mdm_max_initial_distance_m: float = 25.0
    # Unit: meters. Defenders farther than 25m from the ball carrier are generally not in immediate
    # defensive action context for pressing/pressure episodes.
    mdm_distance_closing_min_m: float = 0.8
    # Unit: meters. Minimum reduction in distance between defender and ball carrier for approach MDMs.
    mdm_pass_lane_tolerance_m: float = 2.0
    # Unit: meters. Max distance to line segment between ball carrier and passing option for lane cover.

    # Post-Start Defensive Movement Parameters (Observed WITHOUT MDM/Success filter)
    movement_speed_threshold_mps: float = 1.2
    # Unit: meters per second. Threshold to distinguish active movement onset from stationary positioning.
    # Fundamental research decision: do NOT use high MDM threshold or success filter for 2nd/supporting defenders.
    movement_onset_window_frames: int = 3
    # Consecutive frames above speed threshold to confirm genuine movement onset (filters tracking jitter).

    # Coordination & Simultaneous Responders
    simultaneous_tolerance_frames: int = 2
    # Unit: frames (2 frames = 0.20s). Defenders initiating movements within this window are considered
    # simultaneous responders rather than arbitrarily assigning sequential priority.
    second_defender_max_distance_to_first_m: float = 18.0
    # Unit: meters. Maximum distance from First Defender at Episode Start for a defender to be considered
    # a tactically relevant Second Defender (cover/support). Tactical cover across channels (e.g. central midfielder
    # shifting across to cover full-back) operates up to 18.0m. Defenders beyond 18.0m provide weak-side balance
    # rather than direct cover. If no defender <= 18.0m moves to cover, the press is isolated (second_defender_id = None).

    # Episode Boundaries & Temporal/Spatial Constraints
    min_episode_duration_frames: int = 6  # 0.6 seconds minimum for a meaningful defensive sequence
    max_episode_duration_frames: int = 100  # 10.0 seconds maximum to prevent sprawling disconnected actions
    max_tracking_gap_frames: int = 3  # Maximum consecutive missing frames allowed to linearly interpolate
    post_possession_loss_buffer_frames: int = 10  # 1.0s buffer after possession loss to capture full outcome

    # Progression / Outcome Evaluation Thresholds
    forward_progression_threshold_m: float = 8.0
    # Unit: meters along attacking axis (+x towards opponent goal). >= 8m forward displacement constitutes PROGRESSION.
    shot_box_distance_m: float = 22.0
    # Unit: meters from opponent goal center. Any shot or touch inside danger zone counts toward progression.

    # EPV Parameters
    epv_proxy_fallback_allowed: bool = False  # Do not silently substitute; if True, must be explicitly labelled

    # Execution and output options
    generate_gif: bool = True
    generate_plots: bool = True
    limit_episodes: Optional[int] = None  # Process first N episodes if set (useful for quick validation/testing)
    gif_fps: int = 10  # Output GIF playback frame rate (10 FPS = smooth 1:1 real-time tracking playback)
    gif_context_pre_frames: int = 10  # 1.0s of pre-episode approach context
    gif_context_post_frames: int = 10  # 1.0s of post-episode outcome aftermath context
    verbose: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Instantiate configuration from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def save(self, file_path: Path) -> None:
        """Save configuration to JSON file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> "PipelineConfig":
        """Load configuration from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
