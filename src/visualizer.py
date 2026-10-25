"""Visualization module for defensive response episodes.

Renders high-quality animated GIFs and static tactical trajectory plots
with standard pitch markings, player roles, team legends, motion trails,
and contextual pre/post-roll frames.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image

from src.schema import EpisodeRecord

logger = logging.getLogger(__name__)


def draw_pitch(
    ax: plt.Axes,
    pitch_length: float = 104.0,
    pitch_width: float = 68.0,
    pitch_color: str = "#1e2b24",
    line_color: str = "#ffffff",
) -> None:
    """Draw a scaled soccer pitch centered at (0, 0).

    Pitch coordinates:
    x ranges from -pitch_length/2 to +pitch_length/2
    y ranges from -pitch_width/2 to +pitch_width/2
    """
    hl = pitch_length / 2.0
    hw = pitch_width / 2.0

    # Background
    ax.set_facecolor(pitch_color)

    # Outer boundary
    rect = patches.Rectangle(
        (-hl, -hw), pitch_length, pitch_width,
        linewidth=1.8, edgecolor=line_color, facecolor="none", zorder=1
    )
    ax.add_patch(rect)

    # Halfway line
    ax.plot([0, 0], [-hw, hw], color=line_color, linewidth=1.5, zorder=1)

    # Center circle
    center_circle = patches.Circle((0, 0), 9.15, edgecolor=line_color, facecolor="none", linewidth=1.5, zorder=1)
    ax.add_patch(center_circle)
    ax.plot(0, 0, marker="o", color=line_color, markersize=3, zorder=1)

    # Penalty areas (16.5m x 40.32m)
    box_length = 16.5
    box_width = 40.32
    hbw = box_width / 2.0

    # Left penalty area
    left_box = patches.Rectangle(
        (-hl, -hbw), box_length, box_width,
        linewidth=1.5, edgecolor=line_color, facecolor="none", zorder=1
    )
    ax.add_patch(left_box)

    # Right penalty area
    right_box = patches.Rectangle(
        (hl - box_length, -hbw), box_length, box_width,
        linewidth=1.5, edgecolor=line_color, facecolor="none", zorder=1
    )
    ax.add_patch(right_box)

    # Goal boxes (5.5m x 18.32m)
    goal_box_len = 5.5
    goal_box_w = 18.32
    hgw = goal_box_w / 2.0

    left_goal_box = patches.Rectangle(
        (-hl, -hgw), goal_box_len, goal_box_w,
        linewidth=1.2, edgecolor=line_color, facecolor="none", zorder=1
    )
    ax.add_patch(left_goal_box)

    right_goal_box = patches.Rectangle(
        (hl - goal_box_len, -hgw), goal_box_len, goal_box_w,
        linewidth=1.2, edgecolor=line_color, facecolor="none", zorder=1
    )
    ax.add_patch(right_goal_box)

    # Goals (2.0m depth, 7.32m width)
    left_goal = patches.Rectangle((-hl - 2.0, -3.66), 2.0, 7.32, linewidth=1.2, edgecolor="#aaaaaa", facecolor="none", zorder=1)
    right_goal = patches.Rectangle((hl, -3.66), 2.0, 7.32, linewidth=1.2, edgecolor="#aaaaaa", facecolor="none", zorder=1)
    ax.add_patch(left_goal)
    ax.add_patch(right_goal)

    # Set limits and aspect
    ax.set_xlim(-hl - 4, hl + 4)
    ax.set_ylim(-hw - 4, hw + 4)
    ax.set_aspect("equal")
    ax.axis("off")


class EpisodeVisualizer:
    """Generates visual artifacts (static trajectory plots and animated GIFs)."""

    def __init__(
        self,
        output_dir: Path,
        pitch_length: float = 104.0,
        pitch_width: float = 68.0,
        player_registry: Optional[Dict[int, Dict[str, Any]]] = None,
        teams_dict: Optional[Dict[int, Dict[str, Any]]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.pitch_length = pitch_length
        self.pitch_width = pitch_width
        self.player_registry = player_registry or {}
        self.teams_dict = teams_dict or {}

        self.gifs_dir = self.output_dir / "gifs"
        self.plots_dir = self.output_dir / "trajectories"
        self.gifs_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)

    def _get_team_names(self, episode: EpisodeRecord) -> Tuple[str, str]:
        """Return (defending_team_name, attacking_team_name)."""
        def_name = self.teams_dict.get(episode.defending_team_id, {}).get("name", f"Team {episode.defending_team_id}")
        att_name = self.teams_dict.get(episode.attacking_team_id, {}).get("name", f"Team {episode.attacking_team_id}")
        return def_name, att_name

    def generate_trajectory_plot(
        self,
        episode: EpisodeRecord,
        tracking_frames: List[Dict[str, Any]],
    ) -> Path:
        """Render static 2D trajectory plot with prominent team legend and motion vectors."""
        fig, ax = plt.subplots(figsize=(13, 8.5), dpi=130)
        draw_pitch(ax, self.pitch_length, self.pitch_width)

        def_team_name, att_team_name = self._get_team_names(episode)

        # Highlight Defending Team's Own Half (Wilayah Sendiri)
        att_dir = self.teams_dict.get(episode.attacking_team_id, {}).get("attack_direction_by_period", {}).get(episode.period, "left_to_right")
        hl = self.pitch_length / 2.0
        hw = self.pitch_width / 2.0
        if att_dir == "left_to_right":
            shade_rect = patches.Rectangle((0, -hw), hl, self.pitch_width, facecolor="#00E5FF", alpha=0.045, zorder=1)
            ax.add_patch(shade_rect)
            ax.text(hl / 2, hw - 3.0, "DEFENDING HALF / WILAYAH SENDIRI (x >= 0)", color="#00E5FF", fontsize=8.5, fontweight="bold", alpha=0.6, ha="center")
        else:
            shade_rect = patches.Rectangle((-hl, -hw), hl, self.pitch_width, facecolor="#00E5FF", alpha=0.045, zorder=1)
            ax.add_patch(shade_rect)
            ax.text(-hl / 2, hw - 3.0, "DEFENDING HALF / WILAYAH SENDIRI (x <= 0)", color="#00E5FF", fontsize=8.5, fontweight="bold", alpha=0.6, ha="center")

        # Extract trajectories
        ball_xs, ball_ys = [], []
        player_trajs: Dict[int, Dict[str, List[float]]] = {}

        for f in tracking_frames:
            b = f.get("ball_data", {})
            if b and b.get("x") is not None and b.get("y") is not None:
                ball_xs.append(float(b["x"]))
                ball_ys.append(float(b["y"]))

            for p in f.get("player_data", []):
                pid = p.get("player_id")
                if pid not in player_trajs:
                    player_trajs[pid] = {"xs": [], "ys": []}
                player_trajs[pid]["xs"].append(float(p["x"]))
                player_trajs[pid]["ys"].append(float(p["y"]))

        # Plot ball path
        if ball_xs:
            ax.plot(ball_xs, ball_ys, color="#FFFFFF", linestyle="--", linewidth=1.8, alpha=0.9, label="Ball Trajectory", zorder=3)
            ax.scatter(ball_xs[0], ball_ys[0], color="#FFFFFF", s=60, marker="o", edgecolors="#333333", zorder=4)
            ax.scatter(ball_xs[-1], ball_ys[-1], color="#FFFFFF", s=100, marker="*", edgecolors="#000000", zorder=4)

        first_id = episode.first_defender_id
        second_id = episode.second_defender_id

        # Plot all players
        for pid, traj in player_trajs.items():
            p_info = self.player_registry.get(pid, {})
            team_id = p_info.get("team_id")
            xs, ys = traj["xs"], traj["ys"]
            if not xs:
                continue

            # Role styling
            if pid == first_id:
                # First Defender: Bold Gold / Yellow
                ax.plot(xs, ys, color="#FFD700", linewidth=3.5, alpha=0.95, zorder=6, label=f"1st Defender: {p_info.get('short_name', pid)}")
                ax.scatter(xs[0], ys[0], color="#FFD700", marker="o", s=120, edgecolors="#FFFFFF", linewidth=1.5, zorder=7)
                ax.scatter(xs[-1], ys[-1], color="#FFD700", marker="s", s=140, edgecolors="#000000", linewidth=1.5, zorder=7)
                ax.text(xs[0], ys[0] + 1.3, f"1st: {p_info.get('short_name', pid)}", color="#FFD700", fontsize=9, fontweight="bold", ha="center")
            elif pid == second_id:
                # Second Defender: Bright Orange
                ax.plot(xs, ys, color="#FF9100", linewidth=3.0, alpha=0.95, zorder=5, label=f"2nd Defender: {p_info.get('short_name', pid)}")
                ax.scatter(xs[0], ys[0], color="#FF9100", marker="o", s=100, edgecolors="#FFFFFF", linewidth=1.5, zorder=6)
                ax.scatter(xs[-1], ys[-1], color="#FF9100", marker="s", s=110, edgecolors="#000000", linewidth=1.5, zorder=6)
                ax.text(xs[0], ys[0] + 1.3, f"2nd: {p_info.get('short_name', pid)}", color="#FF9100", fontsize=9, fontweight="bold", ha="center")
            elif team_id == episode.defending_team_id:
                # Supporting Defenders: Cyan
                ax.plot(xs, ys, color="#00E5FF", linewidth=1.2, alpha=0.45, zorder=4)
                ax.scatter(xs[0], ys[0], color="#00E5FF", s=35, alpha=0.6, zorder=4)
            else:
                # Attacking Team: Coral Red
                ax.plot(xs, ys, color="#FF5252", linewidth=1.2, alpha=0.45, zorder=4)
                ax.scatter(xs[0], ys[0], color="#FF5252", s=35, alpha=0.6, zorder=4)

        # Build prominent team legend
        # Dummy artists for clean, explicit team identification
        def_patch = patches.Patch(color="#00E5FF", label=f"DEFENDING TEAM: {def_team_name}")
        att_patch = patches.Patch(color="#FF5252", label=f"ATTACKING TEAM: {att_team_name}")
        first_patch = patches.Patch(color="#FFD700", label=f"1st Defender: {episode.first_defender_name} (Onset: {episode.first_defender_onset_frame})")
        second_patch = patches.Patch(color="#FF9100", label=f"2nd Defender: {episode.second_defender_name or 'None'} (Onset: {episode.second_defender_onset_frame or 'N/A'})")
        ball_line = plt.Line2D([0], [0], color="#FFFFFF", linestyle="--", linewidth=2, label="Ball Trajectory")

        legend_handles = [def_patch, att_patch, first_patch, second_patch, ball_line]
        leg = ax.legend(
            handles=legend_handles,
            loc="upper right",
            facecolor="#18241e",
            edgecolor="#557766",
            labelcolor="#FFFFFF",
            fontsize=9,
            framealpha=0.92,
        )

        # Title & Tactical Annotations
        dv_str = f"{episode.defensive_value:+.4f}" if episode.defensive_value is not None else "N/A"
        ax.set_title(
            f"Episode {episode.episode_id} | Outcome: {episode.main_outcome} ({episode.detailed_outcome})\n"
            f"Start: Frame {episode.episode_start_frame} | End: Frame {episode.episode_end_frame} | "
            f"Duration: {episode.duration_seconds:.1f}s | DV: {dv_str}",
            color="#FFFFFF", fontsize=11, fontweight="bold", pad=12
        )

        plot_path = self.plots_dir / f"{episode.episode_id}_trajectory.png"
        fig.tight_layout()
        fig.savefig(plot_path, facecolor="#141c18", dpi=130)
        plt.close(fig)

        return plot_path

    def generate_gif(
        self,
        episode: EpisodeRecord,
        tracking_index: Dict[int, Dict[str, Any]],
        fps_out: int = 10,
        pre_context_frames: int = 10,
        post_context_frames: int = 10,
    ) -> Path:
        """Render detailed, fluid animated tactical GIF showing step-by-step defensive response.

        Includes:
        - 1:1 real-time 10 FPS tracking playback (no skipping)
        - Pre-episode approach context (1.0s before Episode Start)
        - Post-episode aftermath context (1.0s after Episode End)
        - Dynamic motion trails showing trajectory paths forming in real-time
        - Explicit Team Legend and Attacking Direction banner
        """
        images = []
        first_id = episode.first_defender_id
        second_id = episode.second_defender_id
        def_team_name, att_team_name = self._get_team_names(episode)
        att_dir = self.teams_dict.get(episode.attacking_team_id, {}).get("attack_direction_by_period", {}).get(episode.period, "left_to_right")
        hl = self.pitch_length / 2.0
        hw = self.pitch_width / 2.0

        start_f = max(0, episode.episode_start_frame - pre_context_frames)
        end_f = episode.episode_end_frame + post_context_frames

        # Gather frames in sequence
        frame_list = [tracking_index[f] for f in range(start_f, end_f + 1) if f in tracking_index]
        if not frame_list:
            frame_list = [tracking_index[f] for f in range(episode.episode_start_frame, episode.episode_end_frame + 1) if f in tracking_index]

        # Accumulators for dynamic motion trails
        first_trail_x, first_trail_y = [], []
        second_trail_x, second_trail_y = [], []
        ball_trail_x, ball_trail_y = [], []

        for frame in frame_list:
            fig, ax = plt.subplots(figsize=(12, 7.5), dpi=95)
            draw_pitch(ax, self.pitch_length, self.pitch_width)

            # Highlight Defending Half (Wilayah Sendiri)
            if att_dir == "left_to_right":
                shade_rect = patches.Rectangle((0, -hw), hl, self.pitch_width, facecolor="#00E5FF", alpha=0.045, zorder=1)
                ax.add_patch(shade_rect)
                ax.text(hl / 2, hw - 3.0, "DEFENDING HALF / WILAYAH SENDIRI (x >= 0)", color="#00E5FF", fontsize=8.0, fontweight="bold", alpha=0.6, ha="center")
            else:
                shade_rect = patches.Rectangle((-hl, -hw), hl, self.pitch_width, facecolor="#00E5FF", alpha=0.045, zorder=1)
                ax.add_patch(shade_rect)
                ax.text(-hl / 2, hw - 3.0, "DEFENDING HALF / WILAYAH SENDIRI (x <= 0)", color="#00E5FF", fontsize=8.0, fontweight="bold", alpha=0.6, ha="center")

            f_num = frame.get("frame", 0)
            t_stamp = frame.get("timestamp", "")

            # Determine tactical sequence phase
            if f_num < episode.episode_start_frame:
                phase_label = "[PHASE: PRE-START APPROACH]"
                phase_color = "#AAAAAA"
            elif f_num <= episode.episode_end_frame:
                phase_label = "[PHASE: ACTIVE DEFENSIVE ENGAGEMENT]"
                phase_color = "#FFD700"
            else:
                phase_label = f"[PHASE: OUTCOME FORMED — {episode.main_outcome}]"
                phase_color = "#4FC3F7" if episode.main_outcome != "PROGRESSION" else "#FF5252"

            # Draw ball and record trail
            b = frame.get("ball_data", {})
            if b and b.get("x") is not None and b.get("y") is not None:
                bx, by = float(b["x"]), float(b["y"])
                ball_trail_x.append(bx)
                ball_trail_y.append(by)
                ax.scatter(bx, by, color="#FFFFFF", s=100, edgecolors="#000000", linewidth=1.5, zorder=8)

            # Draw ball trail
            if len(ball_trail_x) > 1:
                ax.plot(ball_trail_x[-15:], ball_trail_y[-15:], color="#FFFFFF", linestyle="--", linewidth=1.5, alpha=0.7, zorder=3)

            # Draw players
            for p in frame.get("player_data", []):
                pid = p.get("player_id")
                px = float(p.get("x", 0.0))
                py = float(p.get("y", 0.0))
                p_info = self.player_registry.get(pid, {})
                team_id = p_info.get("team_id")
                short_name = p_info.get("short_name", str(pid))

                if pid == first_id:
                    first_trail_x.append(px)
                    first_trail_y.append(py)
                    # Highlight 1st defender with bold gold ring
                    circle = patches.Circle((px, py), 1.9, facecolor="#FFD700", edgecolor="#000000", linewidth=2.2, zorder=7)
                    ax.add_patch(circle)
                    ax.text(px, py + 2.3, f"1st: {short_name}", color="#FFD700", fontsize=8.5, fontweight="bold", ha="center")
                elif pid == second_id:
                    second_trail_x.append(px)
                    second_trail_y.append(py)
                    # Highlight 2nd defender with bright orange ring
                    circle = patches.Circle((px, py), 1.7, facecolor="#FF9100", edgecolor="#FFFFFF", linewidth=1.8, zorder=6)
                    ax.add_patch(circle)
                    ax.text(px, py + 2.3, f"2nd: {short_name}", color="#FF9100", fontsize=8.5, fontweight="bold", ha="center")
                elif team_id == episode.defending_team_id:
                    # Supporting Defenders: Light Cyan
                    circle = patches.Circle((px, py), 1.3, facecolor="#00E5FF", edgecolor="#FFFFFF", linewidth=1.0, zorder=5)
                    ax.add_patch(circle)
                    ax.text(px, py + 1.8, short_name, color="#E0F7FA", fontsize=6.5, ha="center")
                else:
                    # Attacking Team: Coral Red
                    circle = patches.Circle((px, py), 1.3, facecolor="#FF5252", edgecolor="#FFFFFF", linewidth=1.0, zorder=5)
                    ax.add_patch(circle)
                    ax.text(px, py + 1.8, short_name, color="#FFCDD2", fontsize=6.5, ha="center")

            # Draw motion trails for 1st and 2nd defenders
            if len(first_trail_x) > 1:
                ax.plot(first_trail_x[-20:], first_trail_y[-20:], color="#FFD700", linewidth=2.5, alpha=0.8, zorder=4)
            if len(second_trail_x) > 1:
                ax.plot(second_trail_x[-20:], second_trail_y[-20:], color="#FF9100", linewidth=2.2, alpha=0.8, zorder=4)

            # Prominent Team Legend Box in Top-Right
            def_patch = patches.Patch(color="#00E5FF", label=f"DEFENDING: {def_team_name}")
            att_patch = patches.Patch(color="#FF5252", label=f"ATTACKING: {att_team_name}")
            first_patch = patches.Patch(color="#FFD700", label=f"1st Defender: {episode.first_defender_name}")
            second_patch = patches.Patch(color="#FF9100", label=f"2nd Defender: {episode.second_defender_name or 'None'}")

            ax.legend(
                handles=[def_patch, att_patch, first_patch, second_patch],
                loc="upper right",
                facecolor="#18241e",
                edgecolor="#557766",
                labelcolor="#FFFFFF",
                fontsize=8.5,
                framealpha=0.92,
            )

            # Top Header Bar
            dv_str = f"{episode.defensive_value:+.4f}" if episode.defensive_value is not None else "N/A"
            header_text = (
                f"Episode {episode.episode_id}  |  Frame: {f_num} ({t_stamp})  |  DV: {dv_str}\n"
                f"{phase_label}  |  Outcome: {episode.main_outcome} ({episode.detailed_outcome})"
            )
            ax.text(
                -self.pitch_length / 2, self.pitch_width / 2 + 1.8,
                header_text,
                color="#FFFFFF", fontsize=9.5, fontweight="bold", ha="left"
            )

            # Render to memory buffer
            buf = io.BytesIO()
            fig.tight_layout()
            fig.savefig(buf, format="png", facecolor="#141c18", dpi=95)
            plt.close(fig)
            buf.seek(0)
            images.append(Image.open(buf).convert("RGB"))

        gif_path = self.gifs_dir / f"{episode.episode_id}.gif"
        if images:
            # Durations: 100ms per frame (10 FPS) for smooth real-time tracking,
            # with an extended 1000ms pause on the final frame so the tactical outcome can be examined
            durations = [int(1000 / fps_out)] * len(images)
            durations[-1] = 1200  # 1.2s freeze on final frame

            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=durations,
                loop=0,
                optimize=True,
            )

        return gif_path
