# From First Pressure to Defensive Response

A research-grade sports analytics and tracking pipeline investigating how the First Defender's defensive movement is followed by secondary and supporting defenders, and how collective defensive movement patterns relate to attacking outcomes and Defensive Value (EPV).

Developed using open tracking (10 FPS) and dynamic event data from SkillCorner.

---

## 1. Research Objectives

- **Primary Goal:** Understand how the first defender's defensive movement is followed by the movements of other defenders, and investigate how these movement patterns relate to the attacking outcome.
- **Scope:** The project does **not** rank individual defenders. Its purpose is to identify patterns of collective defensive coordination (reaction times, support latencies, simultaneous responses, compactness changes, line adjustments) that explain why attacking sequences progress, stall, or end in turnovers.
- **Key Methodological Decision:** All post-start defensive movements are observed **without filtering them by whether they are sufficiently meaningful, effective, or successful**.

---

## 2. Verified Data Source & Dynamic URLs

The pipeline dynamically constructs URLs based on `match_id` without hardcoding:

- **Match Metadata:**  
  `https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/{match_id}/{match_id}_match.json`
- **Dynamic Events:**  
  `https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches/{match_id}/{match_id}_dynamic_events.csv`
- **Extrapolated Tracking (10 FPS):**  
  `https://media.githubusercontent.com/media/SkillCorner/opendata/master/data/matches/{match_id}/{match_id}_tracking_extrapolated.jsonl`

Default validation match: `match_id=1886347` (Auckland FC vs. Newcastle United Jets FC).

---

## 3. Environment Setup & Requirements

### Prerequisites
- Python 3.8+ (tested on Python 3.8, 3.10, 3.14)
- Packages: `requests`, `pandas`, `numpy`, `matplotlib`, `scipy`, `pillow`, `pytest`

### Installation
```bash
pip install -r requirements.txt
```

---

## 4. How to Run the Pipeline

### Default Execution (Full Match 1886347)
Downloads source files directly if not cached, processes all episodes, calculates features, and saves datasets and visuals:
```bash
python -m src.pipeline --match-id 1886347
```

### Specifying a Different Match ID
```bash
python -m src.pipeline --match-id <ANOTHER_MATCH_ID>
```

### Command-Line Options
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--match-id` | int | `1886347` | SkillCorner match ID |
| `--data-dir` | str | `data` | Base directory for raw and processed datasets |
| `--output-dir` | str | `outputs` | Base directory for visuals and run manifest |
| `--config` | str | `None` | Path to optional JSON configuration file |
| `--force-download` | flag | `False` | Force re-download of dataset |
| `--no-gif` | flag | `False` | Disable GIF generation |
| `--limit-episodes` | int | `None` | Process up to N episodes (for quick testing) |
| `--verbose` | flag | `False` | Enable verbose debug logging |

---

## 5. Output Directory Structure

```text
├── data/
│   ├── raw/{match_id}/
│   │   ├── {match_id}_match.json
│   │   ├── {match_id}_dynamic_events.csv
│   │   └── {match_id}_tracking_extrapolated.jsonl
│   └── processed/{match_id}/
│       ├── episodes.csv                  # 1 row per episode (340 rows)
│       ├── defender_movements.csv        # 1 row per defender movement (3,618 rows)
│       ├── episode_defender_features.csv # Episode-level coordination metrics (340 rows)
│       └── episode_validation.csv        # Validation status and review notes (340 rows)
├── outputs/{match_id}/
│   ├── run_manifest.json                 # Execution parameters and summary statistics
│   ├── gifs/                             # Animated tactical GIFs for validation
│   └── trajectories/                     # Static 2D pitch trajectory plots
├── docs/
│   ├── methodology.md                    # Locked research decisions & scientific rules
│   ├── data_dictionary.md                # Full schema definitions, units & provenance
│   ├── algorithm.md                      # Flow diagrams, decision rules & pseudocode
│   └── validation.md                     # Validation protocol & review guidelines
├── src/                                  # Modular pipeline implementation
└── tests/                                # Automated unit and integration test suite
```

---

## 6. Running Automated Tests

Run the full pytest suite (26 unit and integration tests):
```bash
pytest -v
```

---

## 7. Sample Results for Match 1886347 (Own Half Defending / Wilayah Sendiri)

From the complete run manifest (`outputs/1886347/run_manifest.json`):
- **Filtering Constraint:** `only_defending_half = True` (defensive evaluation strictly begins when the ball crosses the halfway line into defending team's own territory).
- **Tactical Proximity Rule:** `second_defender_max_distance_to_first_m = 15.0m` (Second Defender must be in immediate cover distance $\le 15.0\text{ m}$; weak-side defenders $> 15\text{ m}$ away cannot qualify).
- **Total Episodes Detected:** 324
- **Total Defender Movements Tracked:** 3,439
- **Episodes with Identified Second Defender:** 317 (97.8%, average cover distance: 8.75m)
- **Episodes with Isolated Press (No Defender $\le 15$m):** 7 (2.2%)
- **Episodes with Simultaneous Second Responders:** 200 (61.7%)
- **Episodes with Official SkillCorner EPV:** 324 (100%)
- **Outcome Distribution:**
  - `NO_PROGRESSION`: 140 (43.2%)
  - `PROGRESSION`: 132 (40.7%)
  - `TURNOVER`: 52 (16.0%)
- **Mean Episode Duration:** 2.08 seconds

---

## 8. Troubleshooting & Known Limitations

1. **Large Tracking File:** The tracking file is $\approx 85\text{ MB}$ ($59,061$ frames). The pipeline caches downloads locally in `data/raw/{match_id}/`.
2. **Missing Ball Height:** Extrapolated tracking coordinates are projected on the 2D pitch plane ($x \in [-52, 52]$, $y \in [-34, 34]$).
3. **Simultaneous Movements:** Defenders initiating movement within $0.20\text{ s}$ of each other are flagged with `has_simultaneous_second_responders = True` and both IDs are preserved to prevent arbitrary ranking.
