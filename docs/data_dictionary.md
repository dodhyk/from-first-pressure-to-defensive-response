# Data Dictionary — From First Pressure to Defensive Response

This document specifies the complete schema, data types, physical units, provenance, and missing-value behavior for all generated datasets.

---

## 1. `episodes.csv` (Episode-Level Table)

One row per detected defensive episode.

| Field Name | Type | Units | Source | Observed / Derived | Calculation Method / Definition | Missing-Value Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `match_id` | Integer | ID | `match.json` | Observed | SkillCorner unique match ID | Required |
| `episode_id` | String | Format | Generated | Derived | Formatted as `{match_id}_EP_{idx:06d}` | Required |
| `period` | Integer | Half | `dynamic_events.csv` | Observed | Match half (1 or 2) | Required |
| `attacking_team_id` | Integer | ID | `dynamic_events.csv` | Observed | Team ID of the offensive possession | Required |
| `defending_team_id` | Integer | ID | `match.json` | Observed | Team ID of the team defending the sequence | Required |
| `attacking_trigger_type` | String | Categorical | Pipeline | Derived | `player_possession_onset` (evaluated from halfway line entry into defending territory) | Required |
| `attacking_trigger_frame`| Integer | Frames | `dynamic_events.csv` | Observed | Onset frame of the attacking player possession | Required |
| `attacking_trigger_timestamp` | String | `HH:MM:SS.ss` | `dynamic_events.csv` | Observed | Clock timestamp of the attacking possession onset | Required |
| `ball_carrier_id` | Integer | ID | `dynamic_events.csv` | Observed | Attacking player in possession | `NaN` if ball loose |
| `ball_carrier_name` | String | Text | `dynamic_events.csv` | Observed | Short name of the ball carrier | `None` if unknown |
| `episode_start_frame` | Integer | Frames | Extrapolated Tracking | Derived | Frame of the First Defender's qualifying MDM onset | Required |
| `episode_start_timestamp`| String | `HH:MM:SS.ss` | Extrapolated Tracking | Observed | Clock timestamp of Episode Start | Required |
| `episode_end_frame` | Integer | Frames | Tracking & Events | Derived | Frame where outcome forms or interaction terminates | Required |
| `episode_end_timestamp` | String | `HH:MM:SS.ss` | Extrapolated Tracking | Observed | Clock timestamp of Episode End | Required |
| `duration_frames` | Integer | Frames | Derived | Derived | `episode_end_frame - episode_start_frame + 1` | Required |
| `duration_seconds` | Float | Seconds | Derived | Derived | `duration_frames / fps` (10 FPS) | Required |
| `first_defender_id` | Integer | ID | Tracking & Events | Derived | Defender who first satisfies MDM rule | Required |
| `first_defender_name` | String | Text | `match.json` | Observed | Player name of First Defender | Required |
| `first_defender_onset_frame` | Integer | Frames | Tracking | Derived | Frame where First Defender began qualifying MDM | Required |
| `second_defender_id` | Integer | ID | Tracking | Derived | Covering defender within $\le 15.0\text{ m}$ of First Defender with earliest onset | `NaN` if none moved within 15m (isolated press) |
| `second_defender_name` | String | Text | `match.json` | Observed | Player name of Second Defender | `None` if none |
| `second_defender_onset_frame` | Integer | Frames | Tracking | Derived | Frame where Second Defender initiated movement | `NaN` if none |
| `has_simultaneous_second_responders` | Boolean | True/False | Tracking | Derived | `True` if $\ge 2$ defenders initiated onsets within 2 frames | Required |
| `simultaneous_second_defender_ids` | String | CSV IDs | Tracking | Derived | Comma-separated player IDs responding simultaneously | Empty string if single |
| `supporting_defender_ids` | String | CSV IDs | Tracking | Derived | Comma-separated player IDs of all other active defenders | Empty string if none |
| `n_defenders_involved` | Integer | Count | Derived | Derived | Total count of distinct defenders moving in episode | Required |
| `main_outcome` | String | Categorical | Tracking & Events | Derived | `PROGRESSION`, `NO_PROGRESSION`, `TURNOVER`, `UNRESOLVED` | Required |
| `detailed_outcome` | String | Categorical | Tracking & Events | Derived | Granular event/spatial outcome category | Required |
| `epv_against_start` | Float | Probability | `dynamic_events.csv` | Observed | Opponent EPV at Episode Start (`possession_epv_against_start`) | `NaN` if missing |
| `epv_against_end` | Float | Probability | `dynamic_events.csv` | Observed | Opponent EPV at Episode End (`possession_epv_against_end`) | `NaN` if missing |
| `defensive_value` | Float | Probability | Derived | Derived | $\text{DV} = \text{EPV}_{\text{against, start}} - \text{EPV}_{\text{against, end}}$ | `NaN` if missing |
| `epv_source` | String | Text | Pipeline | Derived | `official_skillcorner_dynamic_events` | Required |
| `epv_method` | String | Text | Pipeline | Derived | `possession_epv_against` | Required |
| `epv_missing_status` | String | Categorical | Pipeline | Derived | `available`, `missing_in_dataset`, `values_nan` | Required |
| `data_quality_flags` | String | Text | Pipeline | Derived | Semicolon-separated flags (e.g. `SIMULTANEOUS_SECOND_RESPONDERS`) | `NORMAL` if clean |
| `boundary_reason` | String | Categorical | Pipeline | Derived | `possession_end`, `max_duration_cutoff` | Required |

---

## 2. `defender_movements.csv` (Movement-Level Table)

One row per defender per identified movement segment.

| Field Name | Type | Units | Source | Observed / Derived | Definition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `match_id` | Integer | ID | `match.json` | Observed | Match ID |
| `episode_id` | String | Format | Pipeline | Derived | Associated episode ID |
| `player_id` | Integer | ID | Tracking | Observed | Defender player ID |
| `player_name` | String | Text | `match.json` | Observed | Defender name |
| `team_id` | Integer | ID | `match.json` | Observed | Defending team ID |
| `defender_role` | String | Categorical | Pipeline | Derived | `FIRST_DEFENDER`, `SECOND_DEFENDER`, `SUPPORTING_DEFENDER` |
| `is_simultaneous_responder` | Boolean | True/False | Tracking | Derived | `True` if defender onset tied within simultaneous tolerance |
| `movement_onset_frame` | Integer | Frames | Tracking | Derived | Frame where defender speed crossed $\ge 1.2\text{ m/s}$ |
| `movement_onset_timestamp` | String | `HH:MM:SS.ss` | Tracking | Observed | Timestamp of movement onset |
| `movement_end_frame` | Integer | Frames | Tracking | Derived | Frame where movement segment concluded or episode ended |
| `movement_end_timestamp` | String | `HH:MM:SS.ss` | Tracking | Observed | Timestamp of movement end |
| `movement_duration_seconds`| Float | Seconds | Tracking | Derived | Duration of movement segment in seconds |
| `time_to_onset_from_episode_start_sec` | Float | Seconds | Derived | Derived | Delay from Episode Start to defender movement onset |
| `is_pre_existing_continuation` | Boolean | True/False | Tracking | Derived | `True` if defender was already moving before Episode Start |
| `start_x`, `start_y` | Float | Meters | Tracking | Observed | Coordinates at movement onset (pitch center = 0, 0) |
| `end_x`, `end_y` | Float | Meters | Tracking | Observed | Coordinates at movement end |
| `displacement_x`, `displacement_y` | Float | Meters | Derived | Derived | Net displacement vector along x and y |
| `total_distance` | Float | Meters | Tracking | Derived | Cumulative path distance traversed |
| `mean_speed` | Float | m/s | Tracking | Derived | Average speed over the movement segment |
| `max_speed` | Float | m/s | Tracking | Derived | Peak instantaneous speed over the movement segment |
| `movement_direction_deg` | Float | Degrees | Derived | Derived | Heading angle in degrees $[-180, 180]$ ($0^\circ = +x$) |
| `initial_distance_to_ball` | Float | Meters | Tracking | Derived | Distance to ball/carrier at movement onset |
| `final_distance_to_ball` | Float | Meters | Tracking | Derived | Distance to ball/carrier at movement end |
| `delta_distance_to_ball` | Float | Meters | Derived | Derived | Distance closed toward ball ($\text{initial} - \text{final}$) |
| `is_mdm_qualifying` | Boolean | True/False | Pipeline | Derived | `True` if this segment was the First Defender qualifying MDM |

---

## 3. `episode_defender_features.csv` (Coordination Features Table)

One row per episode summarizing defensive synchronization and spatial geometry.

| Field Name | Type | Units | Definition |
| :--- | :--- | :--- | :--- |
| `match_id` | Integer | ID | Match identifier |
| `episode_id` | String | Format | Episode identifier |
| `second_defender_reaction_time_sec` | Float | Seconds | Time difference between Episode Start and Second Defender onset |
| `first_defender_total_distance` | Float | Meters | Total path distance traveled by First Defender during episode |
| `first_defender_mean_speed` | Float | m/s | Average speed of First Defender during episode |
| `first_defender_approach_vector_angle_to_ball` | Float | Cosine $[-1, 1]$ | Directional alignment between displacement vector and approach to ball |
| `inter_defender_dist_start_first_second` | Float | Meters | Distance between 1st and 2nd defender at Episode Start |
| `inter_defender_dist_end_first_second` | Float | Meters | Distance between 1st and 2nd defender at Episode End |
| `inter_defender_dist_change_first_second` | Float | Meters | Change in distance between 1st and 2nd defender ($\text{end} - \text{start}$) |
| `defensive_compactness_start` | Float | Meters | Outfield defending unit spatial spread radius at Episode Start |
| `defensive_compactness_end` | Float | Meters | Outfield defending unit spatial spread radius at Episode End |
| `compactness_change` | Float | Meters | Change in defending unit spread radius ($\text{end} - \text{start}$) |
| `defensive_line_x_start` | Float | Meters | Longitudinal position of the defensive line at Episode Start |
| `defensive_line_x_end` | Float | Meters | Longitudinal position of the defensive line at Episode End |
| `n_simultaneous_responders` | Integer | Count | Number of defenders responding within simultaneous window |
| `simultaneous_response_tolerance_frames` | Integer | Frames | Configured tolerance window (default: 2 frames = 0.20s) |
| `second_defender_direction_alignment_to_first` | Float | Cosine $[-1, 1]$ | Cosine similarity between First and Second Defender displacement vectors |

---

## 4. `episode_validation.csv` (Audit & Review Table)

| Field Name | Type | Meaning |
| :--- | :--- | :--- |
| `match_id` | Integer | Match ID |
| `episode_id` | String | Episode ID |
| `validation_status` | String | `VALIDATED`, `SIMULTANEOUS_TIE`, `AMBIGUOUS_OUTCOME`, `PROGRESSION_DESPITE_DEFENSE` |
| `validation_tier` | String | Confidence ranking: `HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `REQUIRES_MANUAL_REVIEW` |
| `review_notes` | String | Operational diagnostics and boundary cause |
| `has_gif` | Boolean | Whether an animated GIF was rendered |
| `gif_path` | String | Relative file path to generated GIF |
| `has_trajectory_plot` | Boolean | Whether a static trajectory plot was rendered |
| `plot_path` | String | Relative file path to generated trajectory plot |
