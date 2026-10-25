# Research Methodology — From First Pressure to Defensive Response

## 1. Research Overview and Core Objectives

**Working Title:** From First Pressure to Defensive Response  
**Primary Research Question:** How is the First Defender's meaningful defensive movement followed by the movements of other defenders, and how do these defensive coordination patterns relate to the attacking outcome?

The framework does **not** aim to rank individual defenders or evaluate individual player ratings. Its explicit purpose is to identify patterns of **collective defensive coordination** (e.g., reaction times, secondary support onsets, simultaneous movements, compactness changes, line adjustments) that explain why an attacking sequence progresses, stalls, or results in a turnover.

---

## 2. Locked Methodological Decisions

### 2.1 Unit of Analysis: The Episode
- **Definition:** One continuous defensive sequence is treated as one **episode**.
- **Episode Boundary:** An episode starts at the onset of the qualifying Meaningful Defensive Movement (MDM) of the First Defender. It terminates when the immediate attacking outcome has formed (possession loss, pass completion, shot, clearance, out of bounds) or when the subsequent defensive sequence no longer has a meaningful temporal/spatial relationship with the original MDM.

### 2.2 Attacking Trigger and Halfway Line Boundary (Wilayah Sendiri)
- **Operationalization:** The attacking trigger identifies the specific attacking sequence in which candidate defensive episodes may occur.
- **Halfway Line Constraint (Wilayah Sendiri):** The defensive calculation strictly begins **when the ball crosses the halfway line ($x=0$) and enters the defending team's own half (wilayah sendiri)**:
  - If the attacking team attacks `left_to_right` ($+x$ toward goal at $+52\text{ m}$), the defending team's own half is $x \ge 0$.
  - If the attacking team attacks `right_to_left` ($-x$ toward goal at $-52\text{ m}$), the defending team's own half is $x \le 0$.
- **Temporal Alignment:** If an attacking sequence originates in the attacking team's half, the defensive evaluation window begins at the exact frame the ball crosses the halfway line into defending territory. Possessions occurring entirely in the opponent's defensive third without crossing the halfway line are excluded.
- *Methodological Status Note:* The halfway line crossing establishes the spatial and temporal threshold for defensive engagement in own territory; it triggers candidate First Defender search, while Episode Start is the onset of the First Defender's qualifying MDM.

### 2.3 Candidate First Defender
- **Eligibility:** All outfield defenders of the defending team present on the pitch during the active attacking sequence.
- **Exclusions:** Goalkeepers are excluded from First Defender candidacy to prevent ordinary shot-stopping or penalty-box positioning from initiating tactical pressing episodes.
- **Rule:** The First Defender is **not** automatically selected as the nearest defender to the ball carrier. Eligibility is determined strictly by the earliest qualifying MDM onset.

### 2.4 Meaningful Defensive Movement (MDM)
MDM is a defensive movement meaningfully related to the attacking sequence across three hierarchical evidence layers:

1. **Movement Evidence (Layer 1 — Tracking):**
   - The defender must demonstrate active physical movement exceeding the walking threshold: peak speed $v_{\max} \ge 1.5\text{ m/s}$ and net displacement $\Delta d \ge 0.6\text{ m}$ within a sliding evaluation window ($\le 0.5\text{ s}$). This permits active jockeying, containment, and positional adjustments without artificially rejecting close-range duels.
2. **Defensive Context (Layer 2 — Dynamic Events & Spatial Intent):**
   - Defender is involved in a concurrent SkillCorner `on_ball_engagement` (subtypes: `pressure`, `pressing`, `recovery_press`, `counter_press`, `other`), OR achieves demonstrable spatial closing toward the ball carrier ($\Delta \text{dist} \ge 0.8\text{ m}$), OR is actively engaged in direct duel containment / jockeying where the defender is already in immediate contact distance ($\le 3.5\text{ m}$) to the ball carrier.
   - *Non-Prerequisite Criteria:* Danger reduction indicators (`stop_possession_danger`, `reduce_possession_danger`, `force_backward`) are preserved as supporting evidence but are **not** mandatory success conditions. MDM is not defined solely by whether the defender successfully halts the attack.
3. **Temporal and Spatial Relevance (Layer 3 — Relevance):**
   - The defender's initial distance to the ball carrier must be within $25\text{ m}$ and the movement must not be moving drastically away from the ball carrier ($> 3\text{ m}$ away).

### 2.5 First Defender and Episode Start
- **First Defender:** The eligible defender who first satisfies the three MDM evidence layers during the candidate sequence. When multiple qualifying defenders share the earliest onset tier ($\le 2\text{ frames} = 0.20\text{ s}$), candidate prioritization is resolved by proximity to the ball carrier (`initial_distance_to_ball`), ensuring that the defender directly contesting the duel (e.g., jockeying fullback) is correctly designated as First Defender rather than a distant recovering midfielder sprinting in from deep.
- **Episode Start:** The exact frame and timestamp of that First Defender's qualifying MDM onset.
- *Pipeline Simplification:* As agreed in research specifications, separate "First Pressure" and "Pre-pressure Window" pipeline stages have been permanently removed.

### 2.6 Post-Start Defensive Movements
- **Fundamental Research Principle:** After Episode Start, all defensive movements are observed **without filtering them by whether they are sufficiently meaningful, effective, or successful**.
- **No Second-Defender MDM Filter:** We do **not** use an MDM threshold as a prerequisite for including a movement in post-start analysis. Ineffective, delayed, poorly directed, or passive movements are captured completely to understand failure modes as well as successes.
- **Classification of Defenders:**
  - **First Defender:** Player initiating the episode via qualifying MDM.
  - **Second Defender:** The covering/supporting defender in immediate tactical proximity to the First Defender.
    - *Tactical Proximity Rule:* In football tactical principles (Pressure-Cover-Balance), the covering defender must be in tactical support proximity to the pressing First Defender. Candidates are evaluated within a tactical threshold of $\le 18.0\text{ m}$ (`second_defender_max_distance_to_first_m = 18.0`), accommodating half-space to wide-channel covering sprints.
    - *No Weak-Side Fallback:* Teammates farther than $18.0\text{ m}$ on the opposite flank or deep line are providing team balance/line maintenance, NOT tactical cover. Under no circumstances will a defender $> 18.0\text{ m}$ away be designated as Second Defender.
    - *Movement Evaluation & Priority:* Among candidates within $\le 18.0\text{ m}$, prioritization considers both temporal onset and achieved covering proximity ($d_{\min}$ to First Defender, closing distance). Covering sprints initiating immediately after Episode Start that actively close space toward the First Defender or reach tight support ($\le 8.0\text{ m}$) take precedence over distant static teammates.
    - *Isolated Press:* If no defender within $\le 18.0\text{ m}$ initiates or sustains movement, the sequence represents an isolated/unsupported press, and `second_defender_id` is set to `None` (`NaN`).
  - **Supporting Defenders:** Other outfield defenders whose movements occur during the episode.
- **Onset vs. Continuation:** A defender already moving at speed $\ge 1.2\text{ m/s}$ prior to Episode Start has their movement continuation recorded (`is_pre_existing_continuation = True`). If no candidate within $\le 15.0\text{ m}$ initiates a new onset, an already actively moving defender within $\le 15.0\text{ m}$ can serve as continuous cover.
- **Simultaneous Responders:** If multiple defenders initiate movement onsets within a configurable temporal tolerance ($\Delta t \le 2\text{ frames} = 0.20\text{ s}$), the simultaneous-response information is preserved (`has_simultaneous_second_responders = True` and `simultaneous_second_defender_ids`). The responder closest to the First Defender is designated as primary Second Defender.

### 2.7 Episode Outcomes
Two-level hierarchical outcome structure:

1. **Main Outcome:**
   - `PROGRESSION`: Attack gained significant territorial advancement ($\ge 8\text{ m}$ forward along attacking axis), executed a line break, or generated a shot.
   - `NO_PROGRESSION`: Attack retained possession but was forced backward (recycled to center-backs/goalkeeper), made lateral passes, or stalled.
   - `TURNOVER`: Defending team won possession through tackle, interception, forced clearance, or attacking possession loss.
   - `UNRESOLVED`: Episode evidence is insufficient or ambiguous.
2. **Detailed Outcome:**
   - Granular categories verified by dynamic-event and tracking evidence: `TURNOVER_TACKLE_OR_CHALLENGE`, `TURNOVER_POSSESSION_LOSS`, `PROGRESSION_SHOT`, `PROGRESSION_LINE_BREAK`, `PROGRESSION_TERRITORIAL_GAIN`, `NO_PROGRESSION_RECYCLED_BACK`, `NO_PROGRESSION_LATERAL_OR_STALLED`.

### 2.8 Defensive Value (DV) and EPV
- **Research Convention:**
  $$\text{DV} = \text{EPV}_{\text{against, start}} - \text{EPV}_{\text{against, end}}$$
  where:
  - $\text{EPV}_{\text{against, start}}$ is opponent attacking value at Episode Start.
  - $\text{EPV}_{\text{against, end}}$ is opponent attacking value at Episode End.
  - **Positive DV ($> 0$):** Opponent attacking threat decreased over the defensive sequence (favorable defensive outcome).
  - **Negative DV ($< 0$):** Opponent attacking threat increased over the defensive sequence (favorable attacking outcome).
- **Data Provenance:** Extracted directly from official SkillCorner dynamic-event columns `possession_epv_against_start` and `possession_epv_against_end`. No unverified proxies are substituted.

---

## 3. Assumptions and Known Limitations
1. **Sampling Resolution:** SkillCorner extrapolated tracking is provided at 10 FPS (100 ms per frame). Movement onsets have an intrinsic temporal granularity of $\pm 0.1\text{ s}$.
2. **2D Geometry:** Vertical ball height ($z$) is available in tracking but not used for defender pitch-plane coordinates.
3. **Phase-level Attribution:** EPV metrics reflect SkillCorner possession-phase modeling. When an episode spans transition boundaries, closest possession values are referenced with documented missing-value flags.
