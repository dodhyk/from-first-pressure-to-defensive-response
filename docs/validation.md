# Validation Protocol and Research Quality Assurance

This protocol guides sports scientists and analysts in validating automated episode detections, inspecting visual outputs, and assessing uncertainty.

---

## 1. Visual Inspection Protocol

Visual artifacts are generated in `outputs/{match_id}/gifs/` and `outputs/{match_id}/trajectories/`.

### 1.1 Trajectory Plots (`*_trajectory.png`)
- **Pitch Frame:** 2D top-down view centered at $(0, 0)$.
- **First Defender:** Plotted in bold yellow (`#FFD700`). Marker `o` denotes position at Episode Start; marker `s` denotes position at Episode End.
- **Second Defender:** Plotted in orange (`#FF8C00`).
- **Supporting Defenders:** Plotted in light blue (`#4FC3F7`).
- **Attacking Players:** Plotted in coral (`#FF5252`).
- **Ball Path:** Dashed white line with white circle indicating final ball position.
- **Review Checkpoint:** Verify whether First Defender approach vector aligns with ball carrier trajectory, and verify whether Second Defender was closing support or holding zone.

### 1.2 Animated Tactical GIFs (`*.gif`)
- Rendered at 5 FPS with synchronized match clock and frame index.
- Enables dynamic inspection of:
  1. Pre-existing movement vs. sudden reactive onset.
  2. Defender reaction latency relative to ball arrival.
  3. Spatial line collapse, compacting, or failed recovery runs.

---

## 2. Validation Tiers and Flag Definitions

In `data/processed/{match_id}/episode_validation.csv`, each episode is categorized into one of three confidence tiers:

1. **`HIGH_CONFIDENCE` (`validation_status == 'VALIDATED'`):**
   - Single clear Second Defender onset after Episode Start.
   - Verified dynamic outcome from event and tracking data.
   - Complete EPV start and end data available.
2. **`MEDIUM_CONFIDENCE` (`validation_status == 'SIMULTANEOUS_TIE'`):**
   - Two or more defenders initiated movement onsets within the simultaneous tolerance window ($\le 0.20\text{ s}$).
   - Coordination metrics preserve all simultaneous IDs for multi-defender response analysis.
3. **`REQUIRES_MANUAL_REVIEW` (`validation_status in ['AMBIGUOUS_OUTCOME', 'PROGRESSION_DESPITE_DEFENSE']`):**
   - Sequence reached maximum duration cutoff or outcome was unresolved.
   - Recommended for video review.

---

## 3. False-Positive and False-Negative Checks

### 3.1 Potential False Positives (Detected MDMs that are ordinary drifts)
- **Check:** Filter episodes where First Defender displacement is close to threshold ($\Delta d \approx 1.2\text{ m}$) and no dynamic event occurred.
- **Audit Rule:** Verify whether defender closed distance to ball carrier or whether ball carrier merely dribbled toward a stationary defender.

### 3.2 Potential False Negatives (Missed defensive pressure)
- **Check:** Cross-reference SkillCorner `on_ball_engagement` events where no episode was created.
- **Common Cause:** Ball carrier possession lasted $< 0.5\text{ s}$ (e.g. quick one-touch deflection) before defensive response could organize.

---

## 4. Threshold Sensitivity Guidelines

The pipeline config (`src/config.py`) exposes all operational thresholds:

| Parameter | Default | Plausible Range | Expected Impact of Alteration |
| :--- | :--- | :--- | :--- |
| `mdm_speed_threshold_mps` | $1.5\text{ m/s}$ | $1.2 - 2.0\text{ m/s}$ | Lowering increases episode count; raising isolates aggressive sprints. |
| `mdm_max_initial_distance_m`| $25.0\text{ m}$ | $18.0 - 30.0\text{ m}$| Adjusts sensitivity to cross-field cover adjustments. |
| `simultaneous_tolerance_frames` | $2\text{ frames}$ ($0.2\text{ s}$) | $1 - 4\text{ frames}$ | Controls proportion of episodes classified with simultaneous support. |
| `forward_progression_threshold_m`| $8.0\text{ m}$ | $5.0 - 12.0\text{ m}$ | Higher threshold shifts borderline progressions to `NO_PROGRESSION`. |

---

## 5. Known Uncertainty and Methodological Integrity

1. **Detection Accuracy:** In the absence of third-party manual expert annotations, automated detections provide an empirical research baseline rather than absolute ground truth.
2. **Outcome Decoupling:** Defensive movement inclusion is strictly decoupled from outcome success, ensuring no data leakage between coordination observation and outcome evaluation.
3. **Audit Trail:** All 669 detected episodes record boundary reason, EPV missing status, and data quality flags in `episodes.csv`.
