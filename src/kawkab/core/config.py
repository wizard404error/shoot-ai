"""Centralized configuration for the tracking pipeline.

All thresholds and parameters in one place. Loads from YAML if given,
otherwise uses defaults. This eliminates 70+ hardcoded constants across
cv_service.py, camera_cut_detector.py, pitch_detector.py, etc.

Usage:
    cfg = TrackingConfig.load("configs/broadcast.yaml")
    # or use defaults:
    cfg = TrackingConfig()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DetectionConfig:
    confidence_threshold: float = 0.4
    ball_confidence_threshold: float = 0.15
    iou_threshold: float = 0.5
    max_bbox_area_ratio: float = 0.15
    min_bbox_area_ratio: float = 0.002
    classes: list[int] = field(default_factory=lambda: [0, 32])
    ball_size_min_px: int = 4
    ball_size_max_px: int = 12
    ball_circularity_min: float = 0.6
    tile_overlap: float = 0.2
    enable_tiling: bool = False


@dataclass
class TrackingConfig:
    max_age: int = 30
    min_hits: int = 3
    w_association_emb: float = 0.75
    iou_match_thresh: float = 0.8
    reid_embedding_cap: int = 8
    reid_sample_rate: int = 30
    enable_camera_motion_compensation: bool = False


@dataclass
class FilterConfig:
    expected_player_count: int = 22
    max_keep_top_n: int = 28
    min_track_lifetime_frames: int = 30
    broadcast_frag_ratio_threshold: float = 0.2
    broadcast_stage1_divisor: int = 3000
    broadcast_stage1_pct: float = 0.02
    singlecam_stage1_pct: float = 1.0
    broadcast_stage3_min_segments: int = 2
    broadcast_stage3_min_pct: float = 0.15
    broadcast_stage3_top_k_buffer: int = 3


@dataclass
class StitchConfig:
    spatial_threshold_px: float = 50.0
    temporal_gap_max: float = 2.0
    gap_multiplier: float = 1.5
    overlap_ratio: float = 0.3
    color_distance_threshold: float = 70.0
    face_distance_threshold: float = 0.6
    reid_similarity_threshold: float = 0.6
    reid_few_emb_threshold: float = 0.7
    reid_many_emb_threshold: float = 0.65
    color_few_samples_threshold: float = 70.0
    color_many_samples_threshold: float = 55.0


@dataclass
class CameraCutConfig:
    hue_bins: int = 32
    sat_bins: int = 8
    threshold: float = 0.35
    min_cut_interval: float = 0.5
    sample_every_n: int = 6
    segment_min_frames: int = 6


@dataclass
class PitchDetectionConfig:
    min_line_length: int = 80
    max_line_gap: int = 12
    canny_low: int = 50
    canny_high: int = 150
    hough_threshold: int = 80
    min_confidence: float = 0.15


@dataclass
class ColorConfig:
    pitch_green_lower: list[int] = field(default_factory=lambda: [25, 40, 40])
    pitch_green_upper: list[int] = field(default_factory=lambda: [90, 255, 255])
    n_clusters: int = 3
    white_threshold: int = 230
    black_threshold: int = 30
    min_color_samples: int = 3
    color_sample_rate_hz: float = 2.0
    jpeg_ocr_sample_rate: int = 30


@dataclass
class EventDetectionConfig:
    goal_line_x_ratio: float = 0.05
    min_pass_duration: float = 0.3
    max_pass_duration: float = 6.0
    min_pass_px: float = 50.0
    min_pass_straightness: float = 0.5
    min_shot_px: float = 60.0
    max_shot_duration: float = 1.5
    min_shot_straightness: float = 0.3
    ball_conf_min: float = 0.3
    segment_gap_time: float = 0.5
    segment_max_jump_px: float = 300.0
    shot_dedup_window: float = 2.0
    pass_dedup_window: float = 1.0


@dataclass
class PerformanceConfig:
    frame_skip: int = 6
    checkpoint_interval: int = 500
    enable_checkpoint: bool = False
    gpu_enabled: bool = True
    half_precision: bool = True
    enable_streaming: bool = False
    batch_reid: bool = True


@dataclass
class TrackingConfigRoot:
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    stitch: StitchConfig = field(default_factory=StitchConfig)
    camera_cut: CameraCutConfig = field(default_factory=CameraCutConfig)
    pitch: PitchDetectionConfig = field(default_factory=PitchDetectionConfig)
    color: ColorConfig = field(default_factory=ColorConfig)
    event: EventDetectionConfig = field(default_factory=EventDetectionConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    @classmethod
    def load(cls, path: str | Path) -> TrackingConfigRoot:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {p}")
        with open(p) as f:
            data = json.load(f) if p.suffix == ".json" else _load_yaml(p)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> TrackingConfigRoot:
        root = cls()
        for section_name, section_cls in [
            ("detection", DetectionConfig),
            ("tracking", TrackingConfig),
            ("filter", FilterConfig),
            ("stitch", StitchConfig),
            ("camera_cut", CameraCutConfig),
            ("pitch", PitchDetectionConfig),
            ("color", ColorConfig),
            ("event", EventDetectionConfig),
            ("performance", PerformanceConfig),
        ]:
            if section_name in data:
                section_data = data[section_name]
                current = getattr(root, section_name)
                for field_name in section_cls.__dataclass_fields__:
                    if field_name in section_data:
                        setattr(current, field_name, section_data[field_name])
        return root


def _load_yaml(path: Path) -> dict:
    """Minimal YAML loader — just key:value lines, no nesting."""
    import re
    result: dict[str, Any] = {}
    current_section: str | None = None
    section_data: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        section_match = re.match(r"^(\w+):\s*$", line)
        if section_match:
            if current_section and section_data:
                result[current_section] = dict(section_data)
                section_data = {}
            current_section = section_match.group(1)
            continue
        kv_match = re.match(r"^(\w+):\s*(.+)$", line)
        if kv_match and current_section:
            k, v = kv_match.group(1), kv_match.group(2).strip()
            section_data[k] = _parse_value(v)
    if current_section and section_data:
        result[current_section] = section_data
    return result


def _parse_value(v: str) -> Any:
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    if v.startswith("[") and v.endswith("]"):
        return [_parse_value(x.strip()) for x in v[1:-1].split(",")]
    return v
