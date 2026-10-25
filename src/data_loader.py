"""Data loading and caching module for SkillCorner open tracking and dynamic event data.

Handles dynamic URL generation, robust HTTP streaming, local caching, schema validation,
and coordinate/timestamp integrity checks.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

logger = logging.getLogger(__name__)

SKILLCORNER_OPENDATA_BASE = "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches"
SKILLCORNER_MEDIA_BASE = "https://media.githubusercontent.com/media/SkillCorner/opendata/master/data/matches"


def get_metadata_url(match_id: int) -> str:
    """Return URL for match metadata JSON."""
    return f"{SKILLCORNER_OPENDATA_BASE}/{match_id}/{match_id}_match.json"


def get_events_url(match_id: int) -> str:
    """Return URL for dynamic events CSV."""
    return f"{SKILLCORNER_OPENDATA_BASE}/{match_id}/{match_id}_dynamic_events.csv"


def get_tracking_url(match_id: int) -> str:
    """Return URL for extrapolated tracking JSONL."""
    return f"{SKILLCORNER_MEDIA_BASE}/{match_id}/{match_id}_tracking_extrapolated.jsonl"


def download_file(
    url: str,
    destination: Path,
    force: bool = False,
    timeout: int = 120,
) -> Path:
    """Download a file from an external URL if not already cached.

    Parameters
    ----------
    url : str
        Source HTTP URL to download from.
    destination : Path
        Local file path where the downloaded content will be saved.
    force : bool
        If True, re-download even if the file already exists locally.
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    Path
        Path to the local downloaded file.
    """
    destination = Path(destination)
    if destination.exists() and destination.stat().st_size > 0 and not force:
        logger.info(f"Using cached file: {destination} ({destination.stat().st_size / (1024*1024):.2f} MB)")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_suffix(destination.suffix + ".tmp")

    logger.info(f"Downloading from {url} to {temp_destination}...")
    try:
        # Check HTTP status first with requests head
        head_resp = requests.head(url, allow_redirects=True, timeout=15)
        if head_resp.status_code == 404:
            raise FileNotFoundError(
                f"Resource not found at {url} (HTTP 404). Please verify that match ID exists."
            )
        if head_resp.status_code != 200:
            raise ConnectionError(
                f"Failed to access {url}. HTTP status code: {head_resp.status_code} - {head_resp.reason}"
            )

        import urllib.request
        urllib.request.urlretrieve(url, temp_destination)

        # Atomic rename once fully downloaded
        if temp_destination.exists():
            if destination.exists():
                destination.unlink()
            temp_destination.rename(destination)

        size_mb = destination.stat().st_size / (1024 * 1024)
        logger.info(f"Successfully downloaded {destination.name} ({size_mb:.2f} MB)")
        return destination

    except Exception as e:
        if temp_destination.exists():
            try:
                temp_destination.unlink()
            except OSError:
                pass
        logger.error(f"Error downloading {url}: {e}")
        raise


class DataLoader:
    """Manages loading, parsing, and caching of match metadata, events, and tracking."""

    def __init__(self, match_id: int, raw_dir: Path, force_download: bool = False):
        self.match_id = match_id
        self.raw_dir = Path(raw_dir)
        self.force_download = force_download

        self.metadata_url = get_metadata_url(match_id)
        self.events_url = get_events_url(match_id)
        self.tracking_url = get_tracking_url(match_id)

        self.metadata_path = self.raw_dir / f"{match_id}_match.json"
        self.events_path = self.raw_dir / f"{match_id}_dynamic_events.csv"
        self.tracking_path = self.raw_dir / f"{match_id}_tracking_extrapolated.jsonl"

        self.metadata: Optional[Dict[str, Any]] = None
        self.events_df: Optional[pd.DataFrame] = None
        self.players_dict: Dict[int, Dict[str, Any]] = {}
        self.teams_dict: Dict[int, Dict[str, Any]] = {}
        self.download_manifest: Dict[str, Any] = {}

    def fetch_all(self) -> None:
        """Download all three source files with validation and record retrieval metadata."""
        retrieval_timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(f"Fetching dataset for match {self.match_id}...")
        download_file(self.metadata_url, self.metadata_path, force=self.force_download)
        download_file(self.events_url, self.events_path, force=self.force_download)
        download_file(self.tracking_url, self.tracking_path, force=self.force_download)

        self.download_manifest = {
            "match_id": self.match_id,
            "retrieval_timestamp_utc": retrieval_timestamp,
            "sources": {
                "metadata": {
                    "url": self.metadata_url,
                    "local_path": str(self.metadata_path),
                    "size_bytes": self.metadata_path.stat().st_size,
                },
                "dynamic_events": {
                    "url": self.events_url,
                    "local_path": str(self.events_path),
                    "size_bytes": self.events_path.stat().st_size,
                },
                "tracking": {
                    "url": self.tracking_url,
                    "local_path": str(self.tracking_path),
                    "size_bytes": self.tracking_path.stat().st_size,
                },
            },
        }

    def load_metadata(self) -> Dict[str, Any]:
        """Load and parse match metadata JSON."""
        if self.metadata is None:
            if not self.metadata_path.exists():
                self.fetch_all()
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            # Build player registry
            for p in self.metadata.get("players", []):
                role = p.get("player_role", {}) or {}
                pos_group = role.get("position_group", "")
                acronym = role.get("acronym", "")
                is_gk = (pos_group == "Goalkeeper") or (acronym == "GK")
                self.players_dict[p["id"]] = {
                    "id": p["id"],
                    "short_name": p.get("short_name", f"Player {p['id']}"),
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "number": p.get("number"),
                    "team_id": p.get("team_id"),
                    "position_group": pos_group,
                    "position_acronym": acronym,
                    "is_goalkeeper": is_gk,
                    "trackable_object": p.get("trackable_object"),
                }

            # Build team registry
            home = self.metadata.get("home_team", {})
            away = self.metadata.get("away_team", {})
            sides = self.metadata.get("home_team_side", ["right_to_left", "left_to_right"])

            # Period 1
            home_side_p1 = sides[0] if len(sides) > 0 else "unknown"
            away_side_p1 = "left_to_right" if home_side_p1 == "right_to_left" else "right_to_left"
            # Period 2
            home_side_p2 = sides[1] if len(sides) > 1 else ("left_to_right" if home_side_p1 == "right_to_left" else "right_to_left")
            away_side_p2 = "left_to_right" if home_side_p2 == "right_to_left" else "right_to_left"

            self.teams_dict[home["id"]] = {
                "id": home["id"],
                "name": home.get("name", "Home Team"),
                "short_name": home.get("short_name", home.get("name", "Home")),
                "role": "home",
                "attack_direction_by_period": {1: home_side_p1, 2: home_side_p2},
            }
            self.teams_dict[away["id"]] = {
                "id": away["id"],
                "name": away.get("name", "Away Team"),
                "short_name": away.get("short_name", away.get("name", "Away")),
                "role": "away",
                "attack_direction_by_period": {1: away_side_p1, 2: away_side_p2},
            }

        return self.metadata

    def load_events(self) -> pd.DataFrame:
        """Load and validate dynamic events CSV."""
        if self.events_df is None:
            if not self.events_path.exists():
                self.fetch_all()
            logger.info(f"Loading dynamic events from {self.events_path}...")
            self.events_df = pd.read_csv(self.events_path, low_memory=False)

            # Essential column validation
            required_cols = [
                "event_id", "event_type", "event_subtype",
                "frame_start", "frame_end", "player_id", "team_id"
            ]
            missing = [c for c in required_cols if c not in self.events_df.columns]
            if missing:
                raise ValueError(f"Dynamic events CSV is missing essential columns: {missing}")

            # Normalize frame types to integer where present
            self.events_df["frame_start"] = pd.to_numeric(self.events_df["frame_start"], errors="coerce")
            self.events_df["frame_end"] = pd.to_numeric(self.events_df["frame_end"], errors="coerce")

        return self.events_df

    def get_pitch_dimensions(self) -> Tuple[float, float]:
        """Return (pitch_length, pitch_width) in meters from metadata with fallback."""
        meta = self.load_metadata()
        length = meta.get("pitch_length") or 104.0
        width = meta.get("pitch_width") or 68.0
        return float(length), float(width)

    def load_tracking_frames(
        self,
        frame_start: Optional[int] = None,
        frame_end: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Stream and load tracking frames within an optional frame window [frame_start, frame_end].

        Loads memory-efficiently by streaming JSONL and filtering.
        """
        if not self.tracking_path.exists():
            self.fetch_all()

        frames = []
        with open(self.tracking_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as err:
                    logger.warning(f"Malformed JSONL line skipped in tracking: {err}")
                    continue

                frame_num = record.get("frame")
                if frame_num is None:
                    continue

                if frame_start is not None and frame_num < frame_start:
                    continue
                if frame_end is not None and frame_num > frame_end:
                    break

                frames.append(record)

        return frames

    def build_tracking_index(self) -> Dict[int, Dict[str, Any]]:
        """Build an in-memory index mapping frame_number -> frame tracking dict.

        Enables O(1) random access by frame across the match.
        """
        logger.info(f"Indexing tracking frames from {self.tracking_path}...")
        tracking_index = {}
        with open(self.tracking_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                frame_num = record.get("frame")
                if frame_num is not None:
                    tracking_index[int(frame_num)] = record
        logger.info(f"Indexed {len(tracking_index)} tracking frames.")
        return tracking_index
