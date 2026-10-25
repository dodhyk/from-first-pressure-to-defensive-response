"""Main end-to-end processing pipeline for From First Pressure to Defensive Response.

Orchestrates data fetching, schema normalization, attacking trigger detection,
candidate first defender evaluation, post-start movement tracking,
outcome classification, EPV calculation, visual output rendering, and manifest generation.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np

from src.config import PipelineConfig
from src.data_loader import DataLoader
from src.defensive_value import DefensiveValueCalculator
from src.episode_tracker import EpisodeTracker
from src.mdm_detector import MDMDetector
from src.outcomes import OutcomeEvaluator
from src.schema import (
    DefenderMovementRecord,
    EpisodeDefenderFeatures,
    EpisodeRecord,
    EpisodeValidationRecord,
)
from src.features import is_in_defending_half
from src.visualizer import EpisodeVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DefensivePipeline")


class DefensiveResponsePipeline:
    """End-to-end pipeline processor."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.match_id = config.match_id

        self.raw_dir = Path(config.data_dir) / "raw" / str(self.match_id)
        self.processed_dir = Path(config.data_dir) / "processed" / str(self.match_id)
        self.output_dir = Path(config.output_dir) / str(self.match_id)

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.data_loader = DataLoader(
            match_id=self.match_id,
            raw_dir=self.raw_dir,
            force_download=config.force_download,
        )
        self.outcome_evaluator = OutcomeEvaluator(config)
        self.dv_calculator = DefensiveValueCalculator(config)

    def run(self) -> Dict[str, Any]:
        """Execute the complete pipeline and return execution metrics."""
        t_start = time.time()
        logger.info(f"=== Starting Defensive Response Pipeline for Match ID: {self.match_id} ===")

        # Step 1: Download & Load Data
        self.data_loader.fetch_all()
        metadata = self.data_loader.load_metadata()
        events_df = self.data_loader.load_events()
        pitch_length, pitch_width = self.data_loader.get_pitch_dimensions()
        players_dict = self.data_loader.players_dict
        teams_dict = self.data_loader.teams_dict

        # Step 2: Index Tracking Frames
        tracking_index = self.data_loader.build_tracking_index()

        # Step 3: Initialize Detectors and Trackers
        mdm_detector = MDMDetector(self.config, players_dict)
        episode_tracker = EpisodeTracker(self.config, players_dict)
        visualizer = EpisodeVisualizer(
            output_dir=self.output_dir,
            pitch_length=pitch_length,
            pitch_width=pitch_width,
            player_registry=players_dict,
            teams_dict=teams_dict,
        )

        # Pre-group dynamic events
        engagements_by_player: Dict[int, List[Dict[str, Any]]] = {}
        for _, row in events_df[events_df["event_type"] == "on_ball_engagement"].iterrows():
            pid = row.get("player_id")
            if pd.notna(pid):
                pid = int(pid)
                if pid not in engagements_by_player:
                    engagements_by_player[pid] = []
                engagements_by_player[pid].append(row.to_dict())

        # Step 4: Identify Attacking Triggers
        # Filter player possession events with duration >= min_trigger_duration_frames
        possessions = events_df[events_df["event_type"] == "player_possession"].copy()
        possessions["duration_f"] = possessions["frame_end"] - possessions["frame_start"]
        valid_triggers = possessions[possessions["duration_f"] >= self.config.min_trigger_duration_frames]

        logger.info(f"Identified {len(valid_triggers)} candidate attacking possession sequences.")

        episodes_list: List[EpisodeRecord] = []
        movements_list: List[DefenderMovementRecord] = []
        features_list: List[EpisodeDefenderFeatures] = []
        validation_list: List[EpisodeValidationRecord] = []

        episode_idx = 1
        processed_count = 0

        for _, trig in valid_triggers.iterrows():
            if self.config.limit_episodes and processed_count >= self.config.limit_episodes:
                logger.info(f"Reached configured limit of {self.config.limit_episodes} episodes.")
                break

            trig_frame_start = int(trig["frame_start"])
            trig_frame_end = int(trig["frame_end"])
            trig_period = int(trig.get("period", 1))
            att_team_id = int(trig["team_id"])
            ball_carrier_id = int(trig["player_id"]) if pd.notna(trig["player_id"]) else None
            ball_carrier_name = trig.get("player_name")

            # Determine defending team
            defending_team_id = None
            for t_id in teams_dict:
                if t_id != att_team_id:
                    defending_team_id = t_id
                    break
            if defending_team_id is None:
                continue

            att_direction = teams_dict.get(att_team_id, {}).get("attack_direction_by_period", {}).get(trig_period, "left_to_right")
            def_direction = teams_dict.get(defending_team_id, {}).get("attack_direction_by_period", {}).get(trig_period, "right_to_left")

            # If only_defending_half is enabled, the defensive calculation strictly begins
            # when the ball crosses the halfway line (x=0) into the defending team's own half (wilayah sendiri).
            candidate_start_frame = trig_frame_start
            if self.config.only_defending_half:
                half_entry_frame = None
                for f in range(trig_frame_start, trig_frame_end + 1):
                    if f in tracking_index:
                        b = tracking_index[f].get("ball_data", {})
                        bx = b.get("x")
                        if bx is None and ball_carrier_id:
                            for p in tracking_index[f].get("player_data", []):
                                if p.get("player_id") == ball_carrier_id:
                                    bx = p.get("x")
                                    break
                        if bx is not None and is_in_defending_half(float(bx), att_direction):
                            half_entry_frame = f
                            break

                if half_entry_frame is None:
                    # Sequence never crossed into defending team's own half
                    continue

                candidate_start_frame = half_entry_frame

            # Slice tracking window for trigger sequence starting from own-half entry
            seq_tracking = [
                tracking_index[f]
                for f in range(candidate_start_frame, trig_frame_end + 1)
                if f in tracking_index
            ]
            if len(seq_tracking) < self.config.min_trigger_duration_frames:
                continue

            # Identify candidate defenders on pitch
            active_player_ids: Set[int] = set()
            for f in seq_tracking:
                for p in f.get("player_data", []):
                    pid = p.get("player_id")
                    if pid:
                        active_player_ids.add(int(pid))

            candidate_defenders = mdm_detector.get_candidate_defenders(defending_team_id, active_player_ids)
            if not candidate_defenders:
                continue

            # Find qualifying First Defender and Episode Start
            first_def_info = mdm_detector.find_first_defender_for_episode(
                candidate_defender_ids=candidate_defenders,
                tracking_frames=seq_tracking,
                engagements_by_player=engagements_by_player,
                ball_carrier_id=ball_carrier_id,
            )

            if not first_def_info:
                # No qualifying MDM in this possession sequence
                continue

            first_def_id = first_def_info["player_id"]
            ep_start_frame = first_def_info["onset_frame"]
            ep_start_timestamp = first_def_info.get("onset_timestamp", "")

            # Determine Episode End:
            # Episode continues until attacking possession concludes or max duration reached
            ep_end_frame = min(trig_frame_end, ep_start_frame + self.config.max_episode_duration_frames)
            boundary_reason = "possession_end"
            if ep_end_frame == ep_start_frame + self.config.max_episode_duration_frames:
                boundary_reason = "max_duration_cutoff"

            duration_frames = ep_end_frame - ep_start_frame + 1
            if duration_frames < self.config.min_episode_duration_frames:
                continue

            ep_tracking = [
                tracking_index[f]
                for f in range(ep_start_frame, ep_end_frame + 1)
                if f in tracking_index
            ]
            if len(ep_tracking) < self.config.min_episode_duration_frames:
                continue

            ep_end_timestamp = ep_tracking[-1].get("timestamp", "")
            episode_id = f"{self.match_id}_EP_{episode_idx:06d}"

            # Step 5: Observe ALL post-start defensive movements without MDM/success filter
            moves, second_summary, coord_features = episode_tracker.track_defenders(
                episode_id=episode_id,
                match_id=self.match_id,
                defending_team_id=defending_team_id,
                first_defender_info=first_def_info,
                episode_start_frame=ep_start_frame,
                episode_end_frame=ep_end_frame,
                tracking_index=tracking_index,
                defending_direction=def_direction,
            )

            # Step 6: Evaluate Main and Detailed Outcome
            main_out, det_out, out_evidence = self.outcome_evaluator.evaluate_episode_outcome(
                attacking_team_id=att_team_id,
                defending_team_id=defending_team_id,
                attacking_direction=att_direction,
                episode_start_frame=ep_start_frame,
                episode_end_frame=ep_end_frame,
                ball_carrier_id=ball_carrier_id,
                events_df=events_df,
                tracking_frames=ep_tracking,
            )

            # Step 7: Calculate Defensive Value (DV)
            epv_start, epv_end, dv, epv_prov = self.dv_calculator.calculate_defensive_value(
                attacking_team_id=att_team_id,
                episode_start_frame=ep_start_frame,
                episode_end_frame=ep_end_frame,
                events_df=events_df,
            )

            # Data quality and ambiguity flags
            quality_flags = []
            if second_summary["has_simultaneous_second_responders"]:
                quality_flags.append("SIMULTANEOUS_SECOND_RESPONDERS")
            if boundary_reason == "max_duration_cutoff":
                quality_flags.append("BOUNDARY_MAX_DURATION_REACHED")
            if epv_prov["epv_missing_status"] != "available":
                quality_flags.append(f"EPV_{epv_prov['epv_missing_status'].upper()}")
            if main_out == "UNRESOLVED":
                quality_flags.append("UNRESOLVED_OUTCOME")

            quality_flags_str = ";".join(quality_flags) if quality_flags else "NORMAL"

            supporting_ids = [m.player_id for m in moves if m.defender_role == "SUPPORTING_DEFENDER"]
            unique_supporting_ids = sorted(list(set(supporting_ids)))

            ep_record = EpisodeRecord(
                match_id=self.match_id,
                episode_id=episode_id,
                period=trig_period,
                attacking_team_id=att_team_id,
                defending_team_id=defending_team_id,
                attacking_trigger_type="player_possession_onset",
                attacking_trigger_frame=candidate_start_frame,
                attacking_trigger_timestamp=tracking_index.get(candidate_start_frame, {}).get("timestamp", trig.get("time_start", "")),
                ball_carrier_id=ball_carrier_id,
                ball_carrier_name=ball_carrier_name,
                episode_start_frame=ep_start_frame,
                episode_start_timestamp=ep_start_timestamp,
                episode_end_frame=ep_end_frame,
                episode_end_timestamp=ep_end_timestamp,
                duration_frames=duration_frames,
                duration_seconds=duration_frames / self.config.fps,
                first_defender_id=first_def_id,
                first_defender_name=first_def_info["player_name"],
                first_defender_onset_frame=first_def_info["onset_frame"],
                second_defender_id=second_summary["second_defender_id"],
                second_defender_name=second_summary["second_defender_name"],
                second_defender_onset_frame=second_summary["second_defender_onset_frame"],
                has_simultaneous_second_responders=second_summary["has_simultaneous_second_responders"],
                simultaneous_second_defender_ids=second_summary["simultaneous_second_defender_ids"],
                supporting_defender_ids=",".join(str(i) for i in unique_supporting_ids),
                n_defenders_involved=len(set([first_def_id, second_summary["second_defender_id"]] + unique_supporting_ids) - {None}),
                main_outcome=main_out,
                detailed_outcome=det_out,
                epv_against_start=epv_start,
                epv_against_end=epv_end,
                defensive_value=dv,
                epv_source=epv_prov["epv_source"],
                epv_method=epv_prov["epv_method"],
                epv_missing_status=epv_prov["epv_missing_status"],
                data_quality_flags=quality_flags_str,
                boundary_reason=boundary_reason,
            )

            episodes_list.append(ep_record)
            movements_list.extend(moves)
            features_list.append(coord_features)

            # Validation categorization
            val_status = "VALIDATED"
            val_tier = "HIGH_CONFIDENCE"
            if second_summary["has_simultaneous_second_responders"]:
                val_status = "SIMULTANEOUS_TIE"
                val_tier = "MEDIUM_CONFIDENCE"
            elif main_out == "UNRESOLVED":
                val_status = "AMBIGUOUS_OUTCOME"
                val_tier = "REQUIRES_MANUAL_REVIEW"
            elif main_out == "PROGRESSION":
                val_status = "PROGRESSION_DESPITE_DEFENSE"

            # Render visualization for first 5 episodes or selected samples
            gif_p = ""
            plot_p = ""
            if self.config.generate_plots and episode_idx <= 10:
                plot_file = visualizer.generate_trajectory_plot(ep_record, ep_tracking)
                plot_p = str(plot_file)

            if self.config.generate_gif and episode_idx <= 6:
                gif_file = visualizer.generate_gif(
                    episode=ep_record,
                    tracking_index=tracking_index,
                    fps_out=self.config.gif_fps,
                    pre_context_frames=self.config.gif_context_pre_frames,
                    post_context_frames=self.config.gif_context_post_frames,
                )
                gif_p = str(gif_file)

            validation_list.append(EpisodeValidationRecord(
                match_id=self.match_id,
                episode_id=episode_id,
                validation_status=val_status,
                validation_tier=val_tier,
                review_notes=f"Boundary: {boundary_reason} | Outcome: {det_out}",
                has_gif=bool(gif_p),
                gif_path=gif_p,
                has_trajectory_plot=bool(plot_p),
                plot_path=plot_p,
            ))

            episode_idx += 1
            processed_count += 1

        # Step 8: Save Processed CSV Datasets
        episodes_df = pd.DataFrame([e.to_dict() for e in episodes_list])
        movements_df = pd.DataFrame([m.to_dict() for m in movements_list])
        features_df = pd.DataFrame([f.to_dict() for f in features_list])
        val_df = pd.DataFrame([v.to_dict() for v in validation_list])

        episodes_csv = self.processed_dir / "episodes.csv"
        movements_csv = self.processed_dir / "defender_movements.csv"
        features_csv = self.processed_dir / "episode_defender_features.csv"
        val_csv = self.processed_dir / "episode_validation.csv"

        episodes_df.to_csv(episodes_csv, index=False)
        movements_df.to_csv(movements_csv, index=False)
        features_df.to_csv(features_csv, index=False)
        val_df.to_csv(val_csv, index=False)

        # Step 9: Save Run Manifest
        elapsed = time.time() - t_start
        outcome_counts = episodes_df["main_outcome"].value_counts().to_dict() if not episodes_df.empty else {}
        manifest = {
            "match_id": self.match_id,
            "pipeline_version": "0.1.0",
            "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "execution_duration_seconds": round(elapsed, 2),
            "software_environment": {
                "python": sys.version,
                "pandas": pd.__version__,
                "numpy": np.__version__,
            },
            "source_urls": {
                "metadata": self.data_loader.metadata_url,
                "dynamic_events": self.data_loader.events_url,
                "tracking": self.data_loader.tracking_url,
            },
            "configuration": self.config.to_dict(),
            "summary_statistics": {
                "total_episodes_detected": len(episodes_list),
                "total_defender_movements_tracked": len(movements_list),
                "episodes_with_second_defender": int(episodes_df["second_defender_id"].notna().sum()) if not episodes_df.empty else 0,
                "episodes_with_simultaneous_second_responders": int(episodes_df["has_simultaneous_second_responders"].sum()) if not episodes_df.empty else 0,
                "episodes_with_valid_epv": int(episodes_df["defensive_value"].notna().sum()) if not episodes_df.empty else 0,
                "outcome_distribution": outcome_counts,
                "mean_episode_duration_seconds": float(episodes_df["duration_seconds"].mean()) if not episodes_df.empty else 0.0,
            },
            "output_files": {
                "episodes_csv": str(episodes_csv),
                "defender_movements_csv": str(movements_csv),
                "episode_defender_features_csv": str(features_csv),
                "episode_validation_csv": str(val_csv),
                "trajectories_dir": str(self.output_dir / "trajectories"),
                "gifs_dir": str(self.output_dir / "gifs"),
            },
        }

        manifest_path = self.output_dir / "run_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"=== Pipeline Run Finished in {elapsed:.1f}s ===")
        logger.info(f"Total Episodes Detected: {len(episodes_list)}")
        logger.info(f"Outcome Distribution: {outcome_counts}")
        logger.info(f"Manifest written to: {manifest_path}")

        return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="From First Pressure to Defensive Response Pipeline")
    parser.add_argument("--match-id", type=int, default=1886347, help="SkillCorner match ID (default: 1886347)")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory for raw and processed datasets")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Directory for artifacts, plots, and manifest")
    parser.add_argument("--config", type=str, default=None, help="Path to custom JSON configuration file")
    parser.add_argument("--force-download", action="store_true", help="Force re-download of dataset")
    parser.add_argument("--no-gif", action="store_true", help="Disable GIF animation generation")
    parser.add_argument("--limit-episodes", type=int, default=None, help="Process up to N episodes for quick verification")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.config:
        config = PipelineConfig.load(Path(args.config))
        config.match_id = args.match_id
    else:
        config = PipelineConfig(
            match_id=args.match_id,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            force_download=args.force_download,
            generate_gif=not args.no_gif,
            limit_episodes=args.limit_episodes,
            verbose=args.verbose,
        )

    pipeline = DefensiveResponsePipeline(config)
    manifest = pipeline.run()
    print(json.dumps(manifest["summary_statistics"], indent=2))


if __name__ == "__main__":
    main()
