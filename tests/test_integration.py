"""Integration test for full pipeline run on actual SkillCorner sample match 1886347."""

from pathlib import Path
import json
import pandas as pd
import pytest

from src.config import PipelineConfig
from src.pipeline import DefensiveResponsePipeline


def test_full_pipeline_run_integration():
    """Run pipeline on match 1886347 with limited episodes and assert end-to-end data contracts."""
    config = PipelineConfig(
        match_id=1886347,
        data_dir="data",
        output_dir="outputs",
        force_download=False,
        generate_gif=True,
        generate_plots=True,
        limit_episodes=3,
        verbose=False,
    )

    pipeline = DefensiveResponsePipeline(config)
    manifest = pipeline.run()

    assert manifest["match_id"] == 1886347
    assert manifest["summary_statistics"]["total_episodes_detected"] == 3

    # Check generated files
    proc_dir = Path("data/processed/1886347")
    episodes_file = proc_dir / "episodes.csv"
    movements_file = proc_dir / "defender_movements.csv"
    features_file = proc_dir / "episode_defender_features.csv"
    val_file = proc_dir / "episode_validation.csv"
    manifest_file = Path("outputs/1886347/run_manifest.json")

    assert episodes_file.exists()
    assert movements_file.exists()
    assert features_file.exists()
    assert val_file.exists()
    assert manifest_file.exists()

    df_ep = pd.read_csv(episodes_file)
    assert len(df_ep) == 3
    # Check essential columns
    for col in [
        "match_id", "episode_id", "period", "first_defender_id",
        "second_defender_id", "main_outcome", "detailed_outcome",
        "defensive_value", "epv_source", "data_quality_flags"
    ]:
        assert col in df_ep.columns

    df_mov = pd.read_csv(movements_file)
    assert len(df_mov) > 0
    assert "FIRST_DEFENDER" in df_mov["defender_role"].values
    assert "SECOND_DEFENDER" in df_mov["defender_role"].values
    assert "SUPPORTING_DEFENDER" in df_mov["defender_role"].values

    df_feat = pd.read_csv(features_file)
    assert len(df_feat) == 3
    assert "defensive_compactness_start" in df_feat.columns
    assert "defensive_line_x_start" in df_feat.columns
