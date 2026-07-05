"""Computer Vision service - YOLOv11 + BoT-SORT + ReID.

Handles player, ball, and referee detection + tracking.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncio

import cv2
import numpy as np

from kawkab.core.gpu_acceleration import detect_gpu_tier, recommend_yolo_variant
from kawkab.core.logging import get_logger
from kawkab.services.physical_metrics import compute_physical_metrics
from kawkab.services.track_smoother import TrackSmoother

try:
    from kawkab.services.norfair_tracker import NorfairTracker
    _NORFAIR_AVAILABLE = True
except ImportError:
    _NORFAIR_AVAILABLE = False
    NorfairTracker = None  # type: ignore

_FACE_REC_AVAILABLE = False
FaceRecognitionService = None  # type: ignore
try:
    from kawkab.services.face_recognition_service import FaceRecognitionService
    _FACE_REC_AVAILABLE = True
except ImportError:
    pass

_BOXMOT_AVAILABLE = False
try:
    from boxmot.reid import ReID
    from boxmot.trackers import BotSort
    _BOXMOT_AVAILABLE = True
except ImportError:
    pass

logger = get_logger(__name__)


@dataclass
class Detection:
    """A single object detection."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str
    track_id: int | None = None


@dataclass
class FrameDetections:
    """All detections in a single frame."""

    frame_number: int
    timestamp: float  # seconds
    detections: list[Detection]
    image_width: int
    image_height: int


@dataclass
class MatchTrackData:
    """Complete tracking data for a match."""

    match_id: int
    fps: float
    total_frames: int
    duration_seconds: float
    frames: list[FrameDetections]
    track_registry: dict[int, dict[str, Any]]
    player_teams: dict[int, str] = field(default_factory=dict)
    tracking_metrics: dict[str, Any] = field(default_factory=dict)
    match_type: str = "unknown"
    checkpoint_manager: Any | None = None

    def swap_teams(self) -> None:
        """Swap home/away assignments for all players.

        Useful when the team color clustering heuristic got the labels wrong.
        After calling this, possession/formation stats will be flipped.
        """
        self.player_teams = {
            tid: ("away" if team == "home" else "home" if team == "away" else team)
            for tid, team in self.player_teams.items()
        }
        if "team_detection" in self.tracking_metrics:
            td = self.tracking_metrics["team_detection"]
            if "home_avg_bgr" in td and "away_avg_bgr" in td:
                td["home_avg_bgr"], td["away_avg_bgr"] = (
                    td["away_avg_bgr"],
                    td["home_avg_bgr"],
                )
            if "home_size" in td and "away_size" in td:
                td["home_size"], td["away_size"] = td["away_size"], td["home_size"]


class PipelineCheckpoint:
    """Periodic pipeline state save for crash recovery.

    Writes an atomic HMAC-signed pickle checkpoint every N detection frames.
    On resume, loads the latest checkpoint and fast-forwards past
    already-processed frames, preserving all tracking state.
    """

    _CHECKPOINT_DIR = ".checkpoints"
    _CHECKPOINT_SECRET = b"kawkab-pipeline-ckpt-v2"

    def __init__(self, video_path: Path, frame_skip: int, interval: int = 500):
        self.video_path = video_path.resolve()
        self.frame_skip = frame_skip
        self.interval = interval
        self._last_save_det = -1
        self._ckpt_dir = self.video_path.parent / self._CHECKPOINT_DIR
        self._ckpt_dir.mkdir(parents=True, exist_ok=True)
        self._ckpt_file = self._ckpt_dir / f"{self.video_path.stem}.ckpt"
        self._tmp_file = self._ckpt_file.with_suffix(".tmp")

    def should_save(self, det_idx: int) -> bool:
        return det_idx > 0 and (det_idx - self._last_save_det) >= self.interval

    def save(
        self,
        frame_number: int,
        det_idx: int,
        frames: list,
        track_appearances: dict,
        track_first_frame: dict,
        track_last_frame: dict,
        track_confidence_sum: dict,
        track_is_person: dict,
        track_color_samples: dict,
        track_face_embeddings: dict,
        track_reid_embeddings: dict,
        track_first_px: dict,
        last_detections: list,
        h: int,
        w: int,
        homography_matrix_auto,
        total_frames: int,
        fps: float,
        duration: float,
    ) -> None:
        """Atomically write checkpoint state."""
        self._last_save_det = det_idx
        frames_compact = [
            (
                fdet.frame_number,
                fdet.timestamp,
                [(d.bbox, d.confidence, d.class_id, d.class_name, d.track_id) for d in (fdet.detections or [])],
                fdet.image_width,
                fdet.image_height,
            )
            for fdet in frames
        ]
        last_dets_compact = [
            (d.bbox, d.confidence, d.class_id, d.class_name, d.track_id)
            for d in (last_detections or [])
        ]
        state = {
            "version": 2,
            "video_path": str(self.video_path),
            "total_frames": total_frames,
            "frame_skip": self.frame_skip,
            "fps": fps,
            "duration": duration,
            "frame_number": frame_number,
            "det_idx": det_idx,
            "h": h,
            "w": w,
            "homography_matrix_auto": np.asarray(homography_matrix_auto).tolist() if homography_matrix_auto is not None else None,
            "frames_compact": frames_compact,
            "last_detections_compact": last_dets_compact,
            "track_appearances": dict(track_appearances),
            "track_first_frame": dict(track_first_frame),
            "track_last_frame": dict(track_last_frame),
            "track_confidence_sum": dict(track_confidence_sum),
            "track_is_person": dict(track_is_person),
            "track_color_samples": {str(k): v for k, v in track_color_samples.items()},
            "track_face_embeddings": {str(k): [e.tolist() for e in v] for k, v in track_face_embeddings.items()},
            "track_reid_embeddings": {str(k): [e.tolist() for e in v] for k, v in track_reid_embeddings.items()},
            "track_first_px": {str(k): v for k, v in track_first_px.items()},
        }
        try:
            import hashlib, hmac, pickle as _pk
            # HMAC sign for integrity verification
            payload = _pk.dumps(state, protocol=_pk.HIGHEST_PROTOCOL)
            signature = hmac.new(self._CHECKPOINT_SECRET, payload, hashlib.sha256).hexdigest()
            with open(self._tmp_file, "wb") as f:
                f.write(signature.encode("utf-8") + b"\n" + payload)
            self._tmp_file.rename(self._ckpt_file) if not self._ckpt_file.exists() else (self._ckpt_file.unlink(), self._tmp_file.rename(self._ckpt_file))
            logger.info(f"Checkpoint saved at frame {frame_number} (det {det_idx})")
        except Exception as e:
            logger.warning(f"Checkpoint save failed at frame {frame_number}: {e}")
            if self._tmp_file.exists():
                self._tmp_file.unlink(missing_ok=True)

    @staticmethod
    def latest(video_path: Path) -> dict | None:
        """Return checkpoint state dict if a resume is possible."""
        import hashlib, hmac, pickle as _pk
        ckpt_dir = video_path.resolve().parent / PipelineCheckpoint._CHECKPOINT_DIR
        ckpt_file = ckpt_dir / f"{video_path.stem}.ckpt"
        if not ckpt_file.exists():
            return None
        try:
            with open(ckpt_file, "rb") as f:
                raw = f.read()
            sep = raw.find(b"\n")
            if sep == -1:
                return None
            stored_sig = raw[:sep].decode("utf-8")
            payload = raw[sep + 1:]
            expected_sig = hmac.new(PipelineCheckpoint._CHECKPOINT_SECRET, payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(stored_sig, expected_sig):
                logger.warning("Checkpoint HMAC mismatch — tampered or corrupted file")
                return None
            state = _pk.loads(payload)
            ver = state.get("version", 0)
            if ver < 2:
                logger.warning(f"Checkpoint version {ver} too old, ignoring")
                return None
            return state
        except Exception:
            return None

    def delete(self) -> None:
        """Remove checkpoint after successful completion."""
        try:
            if self._ckpt_file.exists():
                self._ckpt_file.unlink()
            if self._tmp_file.exists():
                self._tmp_file.unlink(missing_ok=True)
        except Exception:
            pass


class CVService:
    """Computer vision pipeline for player/ball detection and tracking.

    v2 improvements:
    - Smart track filtering (min lifetime, bbox area)
    - Bbox area-based filtering for refs/spectators
    - Tracking quality metrics
    - Better noise reduction
    """

    def __init__(
        self,
        model_size: str = "auto",
        confidence_threshold: float = 0.4,
        ball_confidence_threshold: float = 0.15,
        iou_threshold: float = 0.5,
        gpu_enabled: bool = True,
        min_track_lifetime_frames: int = 30,
        min_bbox_area_ratio: float = 0.002,
        max_bbox_area_ratio: float = 0.15,
        expected_player_count: int = 22,
        max_keep_top_n: int = 28,
        model_manager=None,
        tracker_type: str = "deepocsort",
        cfg: Any = None,
        use_track_smoother: bool = False,
    ) -> None:
        # If a TrackingConfigRoot is provided, use its values over defaults
        if cfg is not None:
            d = cfg.detection
            t = cfg.tracking
            f = cfg.filter
            sc = cfg.stitch
            pc = cfg.performance
            cc = cfg.color
            confidence_threshold = d.confidence_threshold
            ball_confidence_threshold = d.ball_confidence_threshold
            iou_threshold = d.iou_threshold
            min_bbox_area_ratio = d.min_bbox_area_ratio
            max_bbox_area_ratio = d.max_bbox_area_ratio
            min_track_lifetime_frames = f.min_track_lifetime_frames
            expected_player_count = f.expected_player_count
            max_keep_top_n = f.max_keep_top_n
            self._cfg = cfg
        else:
            self._cfg = None
        self.use_track_smoother = use_track_smoother
        if model_size == "auto":
            # Check benchmark cache first; fall back to heuristic
            try:
                from kawkab.services.benchmark_service import _load_benchmark_cache

                _gpu_tier = detect_gpu_tier()
                cache = _load_benchmark_cache()
                cache_key = f"gpu_{_gpu_tier}"
                if cache_key in cache:
                    model_size = cache[cache_key]["variant"]
                    logger.info(
                        f"Using benchmark-cached YOLO variant: yolo11{model_size}"
                    )
                else:
                    model_size = recommend_yolo_variant()
            except Exception:
                model_size = recommend_yolo_variant()
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.ball_confidence_threshold = ball_confidence_threshold
        self.iou_threshold = iou_threshold
        self.gpu_enabled = gpu_enabled
        self.tracker_type = tracker_type
        self.min_track_lifetime = min_track_lifetime_frames
        self.min_bbox_area = min_bbox_area_ratio
        self.max_bbox_area = max_bbox_area_ratio
        self.expected_player_count = expected_player_count
        self.max_keep_top_n = max_keep_top_n
        self._model: Any = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._model_manager = model_manager
        self._boxmot_tracker: Any | None = None
        self._ball_tracker: Any | None = None
        gpu_tier = detect_gpu_tier()
        self._use_boxmot = (
            model_size == "auto"
            and _BOXMOT_AVAILABLE
            and gpu_tier in ("medium", "high", "ultra")
        )

        logger.info(
            f"CVService v2: model=yolo11{model_size}, "
            f"conf={confidence_threshold} ball_conf={ball_confidence_threshold}, "
            f"iou={iou_threshold}, gpu={gpu_enabled}, "
            f"min_track_life={min_track_lifetime_frames}, "
            f"max_keep={max_keep_top_n or 'unlimited'}, "
            f"lazy_model={model_manager is not None}"
        )

    async def initialize(self, progress_callback=None) -> None:
        """Lazy-load YOLOv11 model and BoT-SORT tracker.

        Args:
            progress_callback: Called with (progress, message) during model download
        """
        async with self._init_lock:
            if self._initialized:
                return

        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise

        model_name = f"yolo11{self.model_size}.pt"
        logger.info(f"Loading {model_name}...")

        # Use ModelManager for lazy loading if available
        if self._model_manager is not None:
            try:
                model_path = self._model_manager.ensure_model(
                    f"yolo11{self.model_size}",
                    progress_callback=progress_callback,
                )
                logger.info(f"Loading model from {model_path}")
                self._model = YOLO(str(model_path))
            except Exception as e:
                logger.warning(f"ModelManager failed ({e}), falling back to direct YOLO load")
                self._model = YOLO(model_name)
        else:
            self._model = YOLO(model_name)

        if self.gpu_enabled:
            try:
                import torch

                if torch.cuda.is_available():
                    self._model.to("cuda")
                    logger.info("Model loaded on GPU (CUDA)")
                else:
                    logger.warning("GPU not available, using CPU")
            except ImportError:
                logger.warning("PyTorch not installed, cannot check CUDA")

        # Initialize boxmot tracker for deep ReID (OSNet SportsMOT)
        if self._use_boxmot and _BOXMOT_AVAILABLE:
            try:
                self._boxmot_tracker = self._init_boxmot_tracker(self.tracker_type)
            except Exception as e:
                logger.warning(f"boxmot {self.tracker_type} init failed: {e}, using default tracker")

        self._initialized = True
        logger.info("CVService initialized")

    def _init_boxmot_tracker(self, tracker_type: str = "deepocsort"):
        """Lazy-init boxmot tracker with OSNet SportsMOT ReID (v19+ API).

        Args:
            tracker_type: One of "botsort", "deepocsort", "bytetrack", "strongsort",
                         "ocsort", "boosttrack". Falls back to deepocsort on unknown.
        """
        from pathlib import Path
        from kawkab.core.paths import get_paths

        if self._model_manager is not None:
            try:
                model_path_str = self._model_manager.ensure_model("osnet_sportsmot")
                model_path = Path(model_path_str)
            except Exception:
                model_path = get_paths().cache / "models" / "osnet_sportsmot.pt"
        else:
            model_path = get_paths().cache / "models" / "osnet_sportsmot.pt"

        weights = str(model_path) if model_path.exists() else None
        device = "cuda:0" if self.gpu_enabled else "cpu"

        reid_model = None
        if weights:
            reid_model = ReID(
                weights=weights,
                device=device,
                half=self.gpu_enabled,
            )

        tracker_type = tracker_type.lower()
        logger.info(f"Initializing boxmot {tracker_type} with OSNet SportsMOT ReID")

        if tracker_type == "deepocsort":
            from boxmot.trackers.bbox.deepocsort.deepocsort import DeepOcSort
            reid_arg = reid_model.model if reid_model else None
            tracker = DeepOcSort(
                reid_model=reid_arg,
                det_thresh=self.confidence_threshold * 0.8,
                max_age=30,
                min_hits=3,
                iou_threshold=self.iou_threshold,
                w_association_emb=0.75,
                embedding_off=False,
                cmc_off=False,
                per_class=True,
            )
        elif tracker_type == "strongsort":
            from boxmot.trackers.bbox.strongsort.strongsort import StrongSort
            reid_arg = reid_model.model if reid_model else None
            tracker = StrongSort(
                reid_model=reid_arg,
                det_thresh=self.confidence_threshold * 0.8,
                max_age=30,
                min_hits=3,
                iou_threshold=self.iou_threshold,
                per_class=True,
            )
        elif tracker_type == "bytetrack":
            from boxmot.trackers.bbox.bytetrack.bytetrack import ByteTrack
            tracker = ByteTrack(
                track_high_thresh=self.confidence_threshold,
                track_low_thresh=self.ball_confidence_threshold,
                match_thresh=0.8,
                per_class=True,
            )
        else:
            from boxmot.trackers.bbox.botsort.botsort import BotSort
            reid_arg = reid_model.model if reid_model else None
            tracker = BotSort(
                reid_model=reid_arg,
                with_reid=reid_arg is not None,
                track_high_thresh=self.confidence_threshold,
                track_low_thresh=self.ball_confidence_threshold,
                new_track_thresh=self.ball_confidence_threshold,
                per_class=True,
            )
        return tracker

    @staticmethod
    def _get_reid_embedding(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray | None:
        """Extract ReID embedding from a detection.

        Tiers:
          1. boxmot ReID OSNet model (cached singleton) — best quality, uses full frame + bbox
          2. HSV histogram (no model weights required) — fallback, uses crop

        Returns L2-normalized vector or None on failure.
        """
        emb = CVService._extract_boxmot_reid(frame, bbox)
        if emb is not None:
            return emb
        crop = CVService._crop_from_bbox(frame, bbox)
        if crop is None or crop.size == 0:
            return None
        return CVService._histogram_embedding(crop)

    @staticmethod
    def _crop_from_bbox(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray | None:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _init_gpu_reid():
        """Initialize ReID on GPU (cached singleton).

        Priority:
          1. osnet_sportsmot.pt   (football-specific, cached in app dir)
          2. osnet_x1_0_msmt17.pt (full-width OSNet, auto-downloaded by BoxMOT)
          3. default fallback     (tiny x0_25, BoxMOT default)
        """
        import torch
        from kawkab.core.paths import get_paths
        gpu_ok = torch.cuda.is_available()
        sportsmot_path = get_paths().cache / "models" / "osnet_sportsmot.pt"
        if sportsmot_path.exists():
            weights = str(sportsmot_path)
        else:
            weights = "osnet_x1_0_msmt17.pt"  # BoxMOT auto-downloads this
        try:
            reid = ReID(
                weights=weights,
                device="cuda:0" if gpu_ok else "cpu",
                half=gpu_ok,
            )
            setattr(CVService, "_cached_reid_model", reid)
            logger.info(f"ReID model loaded on {'GPU' if gpu_ok else 'CPU'} (weights={weights})")
        except Exception as e:
            logger.debug(f"GPU ReID init failed ({e}), trying CPU fallback")
            try:
                reid = ReID(device="cpu", half=False)
                setattr(CVService, "_cached_reid_model", reid)
            except Exception as e2:
                logger.debug(f"CPU ReID fallback also failed: {e2}")

    @staticmethod
    def _extract_boxmot_reid(frame: np.ndarray, bbox: tuple[float, float, float, float], upscale_factor: int = 2) -> np.ndarray | None:
        """Extract ReID embedding using boxmot's built-in OSNet model.

        Priority: osnet_x1_0 or SportsMOT weights on GPU (fp16).
        Falls back to CPU with default weights.
        If the bbox area is small (< 80x80 px), the crop is upscaled before ReID.
        """
        if not _BOXMOT_AVAILABLE:
            return None
        reid = getattr(CVService, "_cached_reid_model", None)
        if reid is None:
            CVService._init_gpu_reid()
            reid = getattr(CVService, "_cached_reid_model", None)
            if reid is None:
                return None
        try:
            model = reid.model
            x1, y1, x2, y2 = [int(v) for v in bbox]
            bw, bh = x2 - x1, y2 - y1

            # ROI upscale: if region is small, upscale the crop for better ReID
            if upscale_factor > 1 and min(bw, bh) < 80:
                crop = CVService._crop_from_bbox(frame, bbox)
                if crop is not None and crop.size > 0:
                    ch, cw = crop.shape[:2]
                    new_w, new_h = cw * upscale_factor, ch * upscale_factor
                    if new_w > 10 and new_h > 10:
                        upscaled = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                        if hasattr(model, "get_features"):
                            emb = model.get_features(
                                xyxys=np.array([[0, 0, new_w, new_h]], dtype=np.float32),
                                img=upscaled,
                            )
                            if emb is not None and len(emb) > 0:
                                emb_flat = np.asarray(emb[0]).flatten().astype(np.float32)
                                norm = np.linalg.norm(emb_flat)
                                if norm > 1e-8:
                                    return emb_flat / norm
                        elif hasattr(model, "extract"):
                            emb = model.extract(upscaled)
                            if emb is not None and emb.size > 0:
                                emb_flat = emb.flatten().astype(np.float32)
                                norm = np.linalg.norm(emb_flat)
                                if norm > 1e-8:
                                    return emb_flat / norm

            # Default path: full-frame ReID (for larger regions)
            if hasattr(model, "get_features"):
                emb = model.get_features(xyxys=np.array([[x1, y1, x2, y2]], dtype=np.float32), img=frame)
                if emb is not None and len(emb) > 0:
                    emb_flat = np.asarray(emb[0]).flatten().astype(np.float32)
                    norm = np.linalg.norm(emb_flat)
                    if norm > 1e-8:
                        return emb_flat / norm
            elif hasattr(model, "extract"):
                crop = CVService._crop_from_bbox(frame, bbox)
                if crop is not None:
                    emb = model.extract(crop)
                    if emb is not None and emb.size > 0:
                        emb_flat = emb.flatten().astype(np.float32)
                        norm = np.linalg.norm(emb_flat)
                        if norm > 1e-8:
                            return emb_flat / norm
        except Exception as e:
            logger.debug(f"ReID extraction failed: {e}")
        return None

    @staticmethod
    def _histogram_embedding(crop: np.ndarray) -> np.ndarray | None:
        """32-bin per-channel HSV histogram, L2-normalized to unit vector."""
        try:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            hists = []
            for i in range(3):
                hist = cv2.calcHist([hsv], [i], None, [32], [0, 256]).flatten().astype(np.float32)
                hists.append(hist)
            emb = np.concatenate(hists)
            norm = np.linalg.norm(emb)
            if norm > 1e-8:
                return emb / norm
        except Exception:
            pass
        return None

    async def detect_frame(
        self, frame: np.ndarray, frame_number: int, timestamp: float,
        norfair_tracker: Any | None = None,
    ) -> FrameDetections:
        """Run detection (+ optional Norfair tracking) on a single frame.

        When norfair_tracker is provided, uses YOLO detection + Norfair tracking.
        Otherwise falls back to Ultralytics' built-in BoT-SORT tracker.

        Args:
            frame: Image as numpy array (BGR)
            frame_number: Sequential frame index
            timestamp: Time in seconds from video start
            norfair_tracker: Optional NorfairTracker instance for enhanced tracking

        Returns:
            FrameDetections with all detected objects
        """
        if not self._initialized:
            await self.initialize()

        use_norfair = norfair_tracker is not None and _NORFAIR_AVAILABLE
        use_boxmot = self._boxmot_tracker is not None and not use_norfair

        if use_boxmot:
            results = self._model(
                frame, conf=self.ball_confidence_threshold,
                iou=self.iou_threshold, classes=[0, 32], verbose=False,
            )
        elif use_norfair:
            results = self._model(
                frame, conf=self.ball_confidence_threshold,
                iou=self.iou_threshold, classes=[0, 32], verbose=False,
            )
        else:
            results = self._model.track(
                frame, persist=True, conf=self.ball_confidence_threshold,
                iou=self.iou_threshold, classes=[0, 32],
                tracker="botsort.yaml", verbose=False,
            )

        h, w = frame.shape[:2]
        frame_area = w * h
        pitch_mask = self._compute_pitch_mask(frame)

        # Run boxmot BoT-SORT tracking when available (deep ReID via OSNet)
        if use_boxmot and results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                import torch
                dets_np = torch.cat([
                    boxes.xyxy,
                    boxes.conf.unsqueeze(1),
                    boxes.cls.unsqueeze(1),
                ], dim=1).cpu().numpy()
                tracked = self._boxmot_tracker.update(dets_np, frame)
                # Initialize track IDs to -1 for all detections
                boxes.id = torch.full((len(boxes),), -1, dtype=torch.int32)
                if tracked is not None and len(tracked) > 0:
                    for t in tracked:
                        x1, y1, x2, y2, tid, conf, cls_id, *_ = t
                        tid = int(tid)
                        for i in range(len(boxes)):
                            box = boxes.xyxy[i].cpu().numpy()
                            iou = self._bbox_iou(
                                (float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                                (float(x1), float(y1), float(x2), float(y2)),
                            )
                            if iou > 0.5:
                                boxes.id[i] = tid
                                break

        # Collect raw detections
        raw: list[dict[str, Any]] = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                for i in range(len(boxes)):
                    bbox = tuple(boxes.xyxy[i].cpu().numpy())
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())
                    cls_name = self._model.names.get(cls_id, f"class_{cls_id}")
                    tid = (
                        int(boxes.id[i].cpu().numpy())
                        if not use_norfair and boxes.id is not None
                        else None
                    )
                    raw.append({
                        "bbox": bbox, "confidence": conf,
                        "class_id": cls_id, "class_name": cls_name,
                        "track_id": tid,
                    })

        # Filter raw detections
        filtered: list[dict[str, Any]] = []
        for d in raw:
            bbox = d["bbox"]
            conf = d["confidence"]
            cls_name = d["class_name"]
            if cls_name == "person":
                bbox_h = bbox[3] - bbox[1]
                adaptive_thresh = self.confidence_threshold
                if bbox_h < 60:
                    adaptive_thresh = max(0.15, self.confidence_threshold * bbox_h / 60)
                if conf < adaptive_thresh:
                    continue
                area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / frame_area
                if area_ratio < self.min_bbox_area or area_ratio > self.max_bbox_area:
                    continue
                if pitch_mask is not None:
                    foot_x = int((bbox[0] + bbox[2]) / 2)
                    foot_y = int(min(bbox[3] + 5, h - 1))
                    if 0 <= foot_y < h and 0 <= foot_x < w and not pitch_mask[foot_y, foot_x]:
                        continue
            elif cls_name == "sports ball":
                if conf < self.ball_confidence_threshold:
                    continue
                if pitch_mask is not None:
                    bx = int((bbox[0] + bbox[2]) / 2)
                    by = int((bbox[1] + bbox[3]) / 2)
                    if 0 <= by < h and 0 <= bx < w and not pitch_mask[by, bx]:
                        continue
            filtered.append(d)

        # Apply Norfair tracking if available
        if use_norfair and filtered:
            norfair_input = [
                {"bbox": d["bbox"], "confidence": d["confidence"],
                 "label": d["class_name"]}
                for d in filtered
            ]
            tracked = norfair_tracker.update(frame, norfair_input, period=1)
            # Build track_id lookup by label + best IoU match
            from collections import defaultdict
            track_lookup: dict[str, list[tuple[float, int]]] = defaultdict(list)
            for t in tracked:
                track_lookup[t["label"]].append((t["track_id"], t["bbox"]))

            for d in filtered:
                label = d["class_name"]
                best_tid = None
                best_iou = 0.0
                for tid, tbbox in track_lookup.get(label, []):
                    iou = self._bbox_iou(d["bbox"], tbbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_tid = tid
                d["track_id"] = best_tid

        # Build Detection objects
        detections = [
            Detection(
                bbox=d["bbox"], confidence=d["confidence"],
                class_id=d["class_id"], class_name=d["class_name"],
                track_id=d.get("track_id"),
            )
            for d in filtered
        ]

        return FrameDetections(
            frame_number=frame_number, timestamp=timestamp,
            detections=detections, image_width=w, image_height=h,
        )

    async def process_video(
        self,
        video_path: Path,
        progress_callback=None,
        frame_skip: int = 1,
        enable_team_detection: bool = True,
        checkpoint_interval: int = 0,
        resume_checkpoint: dict | None = None,
    ) -> MatchTrackData:
        """Process a full video with smart track filtering (v2).

        Key improvements:
        1. Filter refs/spectators by bbox area
        2. Track lifetime filter (drop noise)
        3. Tracking quality metrics
        4. Confidence tracking per track
        5. Frame skipping (v3): process every Nth frame for 2-4x speedup
        6. Team color detection (v3): k-means on jersey colors
        """
        if not self._initialized:
            await self.initialize()

        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        frame_skip = max(1, int(frame_skip))
        effective_fps = fps / frame_skip
        logger.info(
            f"Processing video: {video_path.name} "
            f"({total_frames} frames, {fps:.1f} FPS, {duration:.1f}s, "
            f"frame_skip={frame_skip}, effective={effective_fps:.1f} FPS)"
        )

        norfair_tracker: Any | None = None
        if _NORFAIR_AVAILABLE and frame_skip <= 3:
            norfair_tracker = NorfairTracker()
            logger.info("Using Norfair tracker (enhanced ReID + camera motion compensation)")

        # Ball tracker — dedicated HSV + Kalman filter, runs at full FPS
        try:
            from kawkab.services.ball_tracker import BallDetection, BallTracker
            self._ball_tracker = BallTracker(fps=fps)
            logger.info("Ball tracker initialized (HSV + Kalman)")
        except Exception as e:
            logger.warning(f"Ball tracker init failed: {e}")
            self._ball_tracker = None

        # Camera cut detection — pre-scan to find broadcast transitions
        camera_cuts: list[int] = []
        try:
            from kawkab.services.camera_cut_detector import CameraCutDetector
            ccd = CameraCutDetector(threshold=0.35, min_cut_interval=0.5)
            cuts_raw = ccd.detect_cuts_fast(video_path)
            camera_cuts = [c["frame"] for c in cuts_raw]
            logger.info(f"Camera cut detection: {len(camera_cuts)} cuts in {video_path.name}")
        except Exception as e:
            logger.debug(f"Camera cut detection skipped: {e}")

        frames: list[FrameDetections] = []
        ball_detections: list[BallDetection] = []
        track_appearances: dict[int, int] = defaultdict(int)
        track_first_frame: dict[int, int] = {}
        track_last_frame: dict[int, int] = {}
        track_confidence_sum: dict[int, float] = defaultdict(float)
        track_is_person: dict[int, bool] = defaultdict(lambda: True)
        track_color_samples: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        track_face_embeddings: dict[int, list[np.ndarray]] = defaultdict(list)
        track_reid_embeddings: dict[int, list[np.ndarray]] = defaultdict(list)
        track_first_px: dict[int, float] = {}
        track_segments: dict[int, set[int]] = defaultdict(set)  # track_id -> set of segment indices
        current_segment = 0
        segment_homography: dict[int, Any] = {}  # segment index -> homography matrix
        prev_det_frame = -frame_skip
        frame_number = 0
        det_idx = 0  # counter for detection frames only
        h, w = 0, 0
        last_detections: list[Detection] = []

        ckpt_mgr = PipelineCheckpoint(video_path, frame_skip, interval=checkpoint_interval) if checkpoint_interval > 0 else None
        resumed_from_checkpoint = False

        # Resume from checkpoint if provided
        if resume_checkpoint is not None and ckpt_mgr is not None:
            import pickle as _pk
            rc = resume_checkpoint
            frame_number = rc["frame_number"]
            det_idx = rc["det_idx"]
            h, w = rc.get("h", 0), rc.get("w", 0)
            homography_matrix_auto = rc.get("homography_matrix_auto")
            resumed_from_checkpoint = True
            ckpt_mgr._last_save_det = det_idx
            # Restore track dicts
            track_appearances.update(rc["track_appearances"])
            track_first_frame.update(rc["track_first_frame"])
            track_last_frame.update(rc["track_last_frame"])
            track_confidence_sum.update(rc["track_confidence_sum"])
            track_is_person.update(rc["track_is_person"])
            track_first_px.update({int(k): v for k, v in rc["track_first_px"].items()})
            track_color_samples.update({int(k): v for k, v in rc["track_color_samples"].items()})
            track_face_embeddings.update({int(k): [np.array(e) for e in v] for k, v in rc["track_face_embeddings"].items()})
            track_reid_embeddings.update({int(k): [np.array(e) for e in v] for k, v in rc["track_reid_embeddings"].items()})
            # Restore frames & last_detections
            for fn, ts, dets, iw, ih in rc["frames_compact"]:
                frame_dets = FrameDetections(
                    frame_number=fn, timestamp=ts,
                    detections=[Detection(*d[:2], d[2], d[3], d[4]) for d in dets] if dets else [],
                    image_width=iw, image_height=ih,
                )
                frames.append(frame_dets)
            last_dets_compact = rc.get("last_detections_compact", [])
            if last_dets_compact:
                last_detections = [Detection(*d[:2], d[2], d[3], d[4]) for d in last_dets_compact]
            # Fast-forward video to resume frame
            seek_to = frame_number + 1  # +1 because frame_number was already processed
            if seek_to < total_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, seek_to)
            logger.info(
                f"Resumed from checkpoint: frame={frame_number}, det={det_idx}, "
                f"frames_in_memory={len(frames)}, seek_to={seek_to}"
            )

        if not resumed_from_checkpoint:
            homography_matrix_auto = None
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                h, w = frame.shape[:2]
                timestamp = frame_number / fps

                # P0-B2: Auto-calibration via PitchDetector on the first processed frame
                if frame_number == 0 and enable_team_detection:
                    try:
                        from kawkab.services.pitch_detector import PitchDetector as _PitchDetector
                        from kawkab.services.homography_service import HomographyService

                        pd = _PitchDetector()
                        guess = pd.detect(frame)
                        if guess.confidence >= 0.15 and len(guess.corners) >= 4:
                            hs = HomographyService()
                            corners_ordered = [
                                guess.corners["tl"],
                                guess.corners["tr"],
                                guess.corners["br"],
                                guess.corners["bl"],
                            ]
                            hm = hs.compute_homography_from_corners(corners_ordered)
                            homography_matrix_auto = hm.matrix
                            logger.info(
                                f"Auto-calibration succeeded: confidence={guess.confidence:.2f}, "
                                f"error={hm.error_px:.2f}px"
                            )
                        else:
                            logger.info(
                                f"Auto-calibration low confidence ({guess.confidence:.2f}), "
                                "falling back to pixel-space analysis"
                            )
                    except Exception as e:
                        logger.debug(f"Auto-calibration failed: {e}")

                if frame_number % frame_skip == 0:
                    # Camera cut: if a cut falls between this detection and previous,
                    # reset boxmot tracker to avoid ID fragmentation across angles.
                    cut_hit = any(
                        cf > prev_det_frame and cf <= frame_number
                        for cf in camera_cuts
                    )
                    if cut_hit or (frame_number == 0 and len(camera_cuts) > 0):
                        if self._boxmot_tracker is not None:
                            try:
                                self._boxmot_tracker = self._init_boxmot_tracker(self.tracker_type)
                                logger.debug(f"Boxmot reset on camera cut at frame {frame_number}")
                            except Exception as e:
                                logger.warning(f"Boxmot reset failed at frame {frame_number}: {e}")
                                # Keep old tracker — detect_frame will skip if None
                        current_segment += 1
                        # Cache homography per camera segment (only once per angle)
                        if current_segment not in segment_homography:
                            try:
                                from kawkab.services.pitch_detector import PitchDetector as _PitchDetector
                                from kawkab.services.homography_service import HomographyService
                                pd = _PitchDetector()
                                guess = pd.detect(frame)
                                if guess.confidence >= 0.15 and len(guess.corners) >= 4:
                                    required_keys = ("tl", "tr", "bl", "br")
                                    if not all(k in guess.corners for k in required_keys):
                                        logger.warning(f"Missing corner keys in calibration guess: {set(required_keys) - set(guess.corners)}")
                                        segment_homography[current_segment] = homography_matrix_auto
                                    else:
                                        corners_ordered = [
                                            guess.corners["tl"], guess.corners["tr"],
                                            guess.corners["br"], guess.corners["bl"],
                                        ]
                                        hs = HomographyService()
                                        hm = hs.compute_homography_from_corners(corners_ordered)
                                        segment_homography[current_segment] = hm.matrix
                                        logger.debug(f"Segment {current_segment} homography cached (conf={guess.confidence:.2f})")
                            except Exception as e:
                                logger.debug(f"Segment {current_segment} homography failed: {e}")
                                segment_homography[current_segment] = homography_matrix_auto

                    try:
                        frame_det = await self.detect_frame(
                            frame, frame_number, timestamp,
                            norfair_tracker=norfair_tracker,
                        )
                    except Exception as e:
                        logger.error(f"detect_frame failed at frame {frame_number}: {e}", exc_info=True)
                        frame_number += 1
                        continue
                    frames.append(frame_det)
                    # Streaming mode: keep sliding window for memory but preserve stitch data
                    if len(frames) > 500:
                        # Keep a compact stitch summary before discarding old frames
                        # Stitch detection uses track_first_frame/track_last_frame/track_color_samples etc.,
                        # which are maintained separately — only frame-level center data is lost.
                        # Slide window instead of destructive truncation:
                        excess = len(frames) - 500
                        frames = frames[excess:]
                    last_detections = frame_det.detections
                    # Ball tracker update (every frame)
                    if self._ball_tracker is not None:
                        ball_det = self._ball_tracker.update(frame, frame_number, timestamp)
                        if ball_det and ball_det.conf > 0.3:
                            ball_detections.append(ball_det)
                    # Track per-segment visibility
                    for det in frame_det.detections:
                        if det.track_id is not None:
                            track_segments[det.track_id].add(current_segment)
                    if enable_team_detection:
                        # Color sampling: immediately on first detection + every ~0.5s
                        for det in frame_det.detections:
                            if det.class_name != "person" or det.track_id is None:
                                continue
                            tid = det.track_id
                            has_color = len(track_color_samples.get(tid, [])) > 0
                            sample_now = not has_color
                            if has_color and det_idx % max(1, int(fps / frame_skip / 2)) == 0:
                                sample_now = True
                            if sample_now:
                                torso = self._extract_torso(frame, det.bbox)
                                if torso is None:
                                    continue
                                color = self._get_dominant_color(torso)
                                if color is not None:
                                    if len(track_color_samples[tid]) < 200:
                                        track_color_samples[tid].append(color)
                    if _FACE_REC_AVAILABLE and det_idx % max(1, int(fps / frame_skip * 2)) == 0:
                        for det in frame_det.detections:
                            if det.class_name != "person" or det.track_id is None:
                                continue
                            torso = self._extract_torso(frame, det.bbox)
                            if torso is None:
                                continue
                            try:
                                if not hasattr(self, "_face_recognition_service") or self._face_recognition_service is None:
                                    self._face_recognition_service = FaceRecognitionService()
                                face_svc = self._face_recognition_service
                                emb = face_svc.get_embedding(torso)
                                if emb is not None and len(track_face_embeddings[det.track_id]) < 36:
                                    track_face_embeddings[det.track_id].append(emb)
                            except Exception:
                                pass
                    # Collect ReID body embeddings every 30 detection frames
                    # (not every frame — batch/sample strategy saves 30x compute)
                    collect_reid = _BOXMOT_AVAILABLE and det_idx % 30 == 0
                    if collect_reid:
                        for det in frame_det.detections:
                            if det.class_name != "person" or det.track_id is None:
                                continue
                            tid = det.track_id
                            if len(track_reid_embeddings.get(tid, [])) >= 36:
                                continue
                            try:
                                emb = self._get_reid_embedding(frame, det.bbox)
                                if emb is not None and emb.size > 0:
                                    track_reid_embeddings[tid].append(emb)
                            except Exception:
                                pass
                    det_idx += 1
                    prev_det_frame = frame_number
                else:
                    frame_det = FrameDetections(
                        frame_number=frame_number,
                        timestamp=timestamp,
                        detections=last_detections,
                        image_width=w,
                        image_height=h,
                    )
                    frames.append(frame_det)

                for det in frame_det.detections:
                    if det.track_id is None:
                        continue
                    tid = det.track_id
                    if frame_number % frame_skip != 0:
                        continue
                    track_appearances[tid] += 1
                    if tid not in track_first_frame:
                        track_first_frame[tid] = frame_number
                        x1, _, x2, _ = det.bbox
                        track_first_px[tid] = (x1 + x2) / 2
                    track_last_frame[tid] = frame_number
                    track_confidence_sum[tid] += det.confidence
                    if det.class_name != "person":
                        track_is_person[tid] = False

                if ckpt_mgr and ckpt_mgr.should_save(det_idx):
                    ckpt_mgr.save(
                        frame_number, det_idx, frames,
                        track_appearances, track_first_frame, track_last_frame,
                        track_confidence_sum, track_is_person,
                        track_color_samples, track_face_embeddings, track_reid_embeddings,
                        track_first_px, last_detections, h, w,
                        homography_matrix_auto, total_frames, fps, duration,
                    )

                frame_number += 1

                if progress_callback and frame_number % (30 * frame_skip) == 0:
                    progress = frame_number / total_frames
                    await progress_callback(
                        progress,
                        f"Processed {frame_number}/{total_frames} frames "
                        f"(skip={frame_skip})",
                    )
        finally:
            cap.release()

        raw_tracks = len(track_appearances)
        effective_total = total_frames // frame_skip
        logger.info(f"Raw tracking: {raw_tracks} unique tracks before filtering (eff_total={effective_total})")

        # Adaptive filtering for broadcast vs single-camera footage
        frag_ratio = raw_tracks / max(1, effective_total)
        if frag_ratio > 0.2:
            first_pass_min_life = max(2, raw_tracks // 3000)
            first_pass_pct = 0.02
            logger.info(f"Broadcast mode: frag_ratio={frag_ratio:.2f}, first_pass_min_life={first_pass_min_life}, first_pass_pct={first_pass_pct}%")
        else:
            first_pass_min_life = min(self.min_track_lifetime, max(5, effective_total // 200))
            first_pass_pct = 1.0
            logger.info(f"Single-cam mode: frag_ratio={frag_ratio:.2f}, first_pass_min_life={first_pass_min_life}, first_pass_pct={first_pass_pct}%")

        # Stage 1: lenient filter to keep fragments for stitching
        first_pass_tracks: set[int] = set()
        for tid, count in track_appearances.items():
            if not track_is_person.get(tid, True):
                continue
            if count < first_pass_min_life:
                continue
            lifetime_pct = (count / max(effective_total, 1)) * 100
            if lifetime_pct < first_pass_pct:
                continue
            first_pass_tracks.add(tid)
        logger.info(
            f"Stage 1 filter: keeping {len(first_pass_tracks)}/{raw_tracks} tracks "
            f"(min_life={first_pass_min_life}, pct={first_pass_pct}%)"
        )

        # P0-A1: Post-hoc track stitching — merge fragments of the same player
        # Run on first_pass_tracks (lenient filter) so Mode C can merge before final filter
        stitch_map = self._detect_track_stitches(
            frames, first_pass_tracks,
            track_first_frame, track_last_frame,
            fps, track_color_samples,
            track_face_embeddings=track_face_embeddings if track_face_embeddings else None,
            track_reid_embeddings=track_reid_embeddings if track_reid_embeddings else None,
        )
        if stitch_map:
            logger.info(
                f"Track stitching: merging {len(stitch_map)} fragments "
                f"({len(first_pass_tracks)} → {len(first_pass_tracks) - len(stitch_map)} unique tracks)"
            )
            for fdet in frames:
                for det in fdet.detections:
                    if det.track_id is not None and det.track_id in stitch_map:
                        det.track_id = stitch_map[det.track_id]
            for discarded, survivor in stitch_map.items():
                if discarded in track_appearances:
                    track_appearances[survivor] = track_appearances.get(survivor, 0) + track_appearances.pop(discarded, 0)
                if discarded in track_first_frame:
                    if track_first_frame[discarded] < track_first_frame.get(survivor, float("inf")):
                        track_first_frame[survivor] = track_first_frame[discarded]
                    del track_first_frame[discarded]
                if discarded in track_last_frame:
                    if track_last_frame[discarded] > track_last_frame.get(survivor, -1):
                        track_last_frame[survivor] = track_last_frame[discarded]
                    del track_last_frame[discarded]
                if discarded in track_confidence_sum:
                    track_confidence_sum[survivor] = track_confidence_sum.get(survivor, 0.0) + track_confidence_sum.pop(discarded, 0)
                if discarded in track_is_person:
                    track_is_person[survivor] = track_is_person.get(survivor, True) or track_is_person.pop(discarded, True)
                if discarded in track_first_px:
                    if survivor not in track_first_px:
                        track_first_px[survivor] = track_first_px[discarded]
                    del track_first_px[discarded]
                if discarded in track_color_samples:
                    track_color_samples[survivor].extend(track_color_samples.pop(discarded, []))
                if discarded in track_segments:
                    track_segments[survivor].update(track_segments.pop(discarded, set()))
                first_pass_tracks.discard(discarded)
            logger.info(f"After stitching: {len(first_pass_tracks)} tracks remain")

        # Stage 3: Final filter — adaptive thresholds on stitched tracks
        final_min_life = min(self.min_track_lifetime, max(5, effective_total // 200))
        # For broadcast with high fragmentation, use lower threshold
        stitched_count = len(first_pass_tracks)
        if frag_ratio > 0.2 and stitched_count > self.expected_player_count:
            # Broadcast: keep tracks with high segment coverage OR high frame coverage
            min_segments = 2
            min_pct = 0.15
            valid_player_tracks = set()
            segment_tracks = sorted(
                first_pass_tracks,
                key=lambda tid: len(track_segments.get(tid, set())),
                reverse=True,
            )
            for tid in segment_tracks:
                if not track_is_person.get(tid, True):
                    continue
                seg_count = len(track_segments.get(tid, set()))
                lifetime_pct = (track_appearances.get(tid, 0) / max(effective_total, 1)) * 100
                # Keep if visible in enough segments OR has substantial frame coverage
                if seg_count >= min_segments or lifetime_pct >= min_pct:
                    valid_player_tracks.add(tid)
                if len(valid_player_tracks) >= self.expected_player_count + 3:
                    break
            logger.info(
                f"Stage 3 broadcast filter: {len(valid_player_tracks)}/{len(first_pass_tracks)} tracks "
                f"(min_segments={min_segments} or min_pct={min_pct}%, top_k={self.expected_player_count + 3})"
            )
        else:
            valid_player_tracks = set()
            for tid in first_pass_tracks:
                count = track_appearances.get(tid, 0)
                if not track_is_person.get(tid, True):
                    continue
                if count < final_min_life:
                    continue
                lifetime_pct = (count / max(effective_total, 1)) * 100
                if lifetime_pct < 1.0:
                    continue
                valid_player_tracks.add(tid)
            logger.info(
                f"Stage 3 final filter: {len(valid_player_tracks)}/{len(first_pass_tracks)} tracks "
                f"(min_life={final_min_life}, pct=1.0%)"
            )

        if self.max_keep_top_n and len(valid_player_tracks) > self.max_keep_top_n:
            top_by_lifetime = sorted(
                valid_player_tracks,
                key=lambda tid: track_appearances[tid],
                reverse=True,
            )
            valid_player_tracks = set(top_by_lifetime[:self.max_keep_top_n])

        # Post-processing: RTS Kalman track smoothing (optional)
        if self.use_track_smoother and frames:
            try:
                smoother = TrackSmoother(dt=1.0 / fps)
                for tid in valid_player_tracks:
                    t_frames: list[int] = []
                    t_positions: list[tuple[float, float]] = []
                    for fdet in frames:
                        for det in fdet.detections:
                            if det.track_id == tid:
                                cx = (det.bbox[0] + det.bbox[2]) / 2.0
                                cy = float(det.bbox[3])
                                t_frames.append(fdet.frame_number)
                                t_positions.append((cx, cy))
                    if len(t_positions) >= 3:
                        smoothed = smoother.smooth(t_frames, t_positions)
                        idx = 0
                        for fdet in frames:
                            for det in fdet.detections:
                                if det.track_id == tid:
                                    w = det.bbox[2] - det.bbox[0]
                                    h = det.bbox[3] - det.bbox[1]
                                    sx, sy = smoothed[idx]
                                    det.bbox = (sx - w / 2, sy - h, sx + w / 2, sy)
                                    idx += 1
                logger.info(f"Track smoothing applied to {len(valid_player_tracks)} tracks")
            except Exception as e:
                logger.warning(f"Track smoothing failed: {e}", exc_info=True)

        track_registry: dict[int, dict[str, Any]] = {}
        for tid in valid_player_tracks:
            track_registry[tid] = {
                "track_id": tid,
                "class_name": "person",
                "first_seen": track_first_frame.get(tid, 0) / fps,
                "last_seen": track_last_frame.get(tid, 0) / fps,
                "frames_tracked": track_appearances[tid],
                "lifetime_pct": (track_appearances[tid] / total_frames) * 100,
                "confidence_avg": track_confidence_sum[tid] / max(1, track_appearances[tid]),
                "first_pixel_x": track_first_px.get(tid),
            }

        fragmentation_rate = raw_tracks / max(1, len(valid_player_tracks))

        count_ratio = len(valid_player_tracks) / max(1, self.expected_player_count)
        quality = self._assess_tracking_quality(fragmentation_rate, count_ratio)

        logger.info(
            f"After filtering: {len(valid_player_tracks)} validated player tracks "
            f"(raw: {raw_tracks}, fragmentation: {fragmentation_rate:.2f}x, "
            f"count ratio: {count_ratio:.2f}x, quality: {quality})"
        )

        player_teams: dict[int, str] = {}
        team_detection_info: dict[str, Any] = {
            "enabled": enable_team_detection,
            "assigned": 0,
            "n_clusters": 0,
            "color_samples": 0,
        }
        if enable_team_detection and track_color_samples:
            try:
                track_color_samples = {
                    tid: samples
                    for tid, samples in track_color_samples.items()
                    if tid in valid_player_tracks
                }
                if not track_color_samples:
                    logger.warning(
                        "No color samples for valid tracks (all samples were from "
                        "invalid/low-lifetime tracks)"
                    )
                else:
                    logger.info(
                        f"Team color clustering on {len(track_color_samples)} valid tracks "
                        f"with {sum(len(s) for s in track_color_samples.values())} samples"
                    )
                    color_data: dict[int, dict] = {}
                    clusters: dict[int, str] = {}
                    for tid, samples in track_color_samples.items():
                        if len(samples) < 3:
                            continue
                        avg = (
                            int(np.mean([c[0] for c in samples])),
                            int(np.mean([c[1] for c in samples])),
                            int(np.mean([c[2] for c in samples])),
                        )
                        color_data[tid] = {
                            "primary_color": avg,
                            "color_hex": f"#{avg[2]:02x}{avg[1]:02x}{avg[0]:02x}",
                            "samples": len(samples),
                        }
                    team_detection_info["color_samples"] = sum(
                        r["samples"] for r in color_data.values()
                    )
                    clusters = self._cluster_team_colors(color_data, n_clusters=3)
                for tid, label in clusters.items():
                    if tid in color_data:
                        color_data[tid]["team_label"] = label
                cluster_avg_bgr: dict[str, tuple[int, int, int]] = {}
                for label in set(clusters.values()):
                    members = [
                        color_data[tid]["primary_color"]
                        for tid, l in clusters.items()
                        if l == label and tid in color_data
                    ]
                    if members:
                        cluster_avg_bgr[label] = (
                            int(np.mean([m[0] for m in members])),
                            int(np.mean([m[1] for m in members])),
                            int(np.mean([m[2] for m in members])),
                        )
                if cluster_avg_bgr:
                    logger.info(
                        f"Cluster BGR colors: "
                        + ", ".join(
                            f"{label}={color}"
                            for label, color in cluster_avg_bgr.items()
                        )
                    )
                for tid, label in clusters.items():
                    if label in ("home", "away") and tid in color_data:
                        player_teams[tid] = label
                    elif label == "referee":
                        logger.debug(f"Track {tid} classified as referee")
                team_detection_info["assigned"] = len(player_teams)
                team_detection_info["n_clusters"] = len(set(clusters.values()))
                home_members = [tid for tid, l in clusters.items() if l == "home"]
                away_members = [tid for tid, l in clusters.items() if l == "away"]
                ref_members = [tid for tid, l in clusters.items() if l == "referee"]
                team_detection_info["home_size"] = len(home_members)
                team_detection_info["away_size"] = len(away_members)
                team_detection_info["ref_size"] = len(ref_members)
                team_detection_info["home_avg_bgr"] = cluster_avg_bgr.get("home")
                team_detection_info["away_avg_bgr"] = cluster_avg_bgr.get("away")
                logger.info(
                    f"Team detection: home={len(home_members)} away={len(away_members)}"
                    + (f" ref={len(ref_members)}" if ref_members else "")
                    + f" (from {len(player_teams)}/{len(valid_player_tracks)} valid tracks)"
                )
            except Exception as e:
                logger.warning(f"Team detection failed: {e}", exc_info=True)

        # Match type inference
        match_type = "unknown"
        avg_track_span = 0.0
        if duration >= 4800:  # 80+ minutes = full match
            match_type = "full_match"
        elif duration < 1200:  # under 20 minutes = highlight
            match_type = "highlight"
        else:
            # Ambiguous: use heuristics
            if valid_player_tracks:
                spans = [
                    (track_last_frame.get(tid, 0) - track_first_frame.get(tid, 0)) / fps
                    for tid in valid_player_tracks
                ]
                avg_track_span = sum(spans) / len(spans)
            if fragmentation_rate < 2.0 and avg_track_span >= 60:
                match_type = "full_match"
            elif fragmentation_rate >= 3.0 or avg_track_span < 15:
                match_type = "highlight"
        logger.info(
            f"Match type inference: {match_type} "
            f"(duration={duration:.0f}s, fragmentation={fragmentation_rate:.2f}, "
            f"avg_span={avg_track_span:.1f}s)"
        )

        # MOT self-consistency metrics + secondary merge map
        mot_metrics: dict[str, Any] = {}
        tracking_merge_map: dict[int, int] = {}
        if _NORFAIR_AVAILABLE:
            try:
                from kawkab.services.tracking_metrics import (
                    compute_tracking_self_metrics,
                    compute_merge_map_from_switches,
                )

                mot_metrics = compute_tracking_self_metrics(
                    frames, track_registry, fps
                )
                # Build track_frames for merge map computation
                track_frames_for_merge: dict[int, set[int]] = {}
                for fdet in frames:
                    fn = fdet.frame_number
                    for det in fdet.detections:
                        if det.class_name != "person" or det.track_id is None:
                            continue
                        tid = det.track_id
                        if tid not in track_frames_for_merge:
                            track_frames_for_merge[tid] = set()
                        track_frames_for_merge[tid].add(fn)
                if track_frames_for_merge:
                    tracking_merge_map = compute_merge_map_from_switches(
                        frames, track_frames_for_merge, fps,
                    )
                    if tracking_merge_map:
                        logger.info(
                            f"Tracking-metrics merge map: {len(tracking_merge_map)} additional candidates"
                        )
            except Exception as e:
                logger.warning(f"MOT self-metrics failed: {e}")

        # Physical metrics via homography (pixel → world coords)
        physical_profiles: dict[int, Any] = {}
        if homography_matrix_auto is not None and frames:
            try:
                track_positions: dict[int, list[tuple[int, float, float, float]]] = defaultdict(list)
                sorted_cuts = sorted(camera_cuts)
                for fdet in frames:
                    fn = fdet.frame_number
                    seg = sum(1 for c in sorted_cuts if c <= fn)
                    hm = segment_homography.get(seg, homography_matrix_auto)
                    if hm is None:
                        continue
                    for det in fdet.detections:
                        if det.class_name != "person" or det.track_id is None:
                            continue
                        foot_x = (det.bbox[0] + det.bbox[2]) / 2.0
                        foot_y = float(det.bbox[3])
                        px = np.array([foot_x, foot_y, 1.0])
                        wld = hm @ px
                        if abs(wld[2]) > 1e-9:
                            wx = wld[0] / wld[2]
                            wy = wld[1] / wld[2]
                            track_positions[det.track_id].append((fn, wx, wy, fdet.timestamp))
                if track_positions:
                    raw_profiles = compute_physical_metrics(dict(track_positions), fps, half_duration_s=2700.0)
                    physical_profiles = {
                        str(k): {
                            "total_distance_m": v.total_distance_m,
                            "avg_speed_kmh": v.avg_speed_kmh,
                            "max_speed_kmh": v.max_speed_kmh,
                            "sprint_count": v.sprint_count,
                            "sprint_distance_m": v.sprint_distance_m,
                            "high_intensity_distance_m": v.high_intensity_distance_m,
                            "jogging_distance_m": v.jogging_distance_m,
                            "walking_distance_m": v.walking_distance_m,
                            "standing_time_s": v.standing_time_s,
                            "total_active_time_s": v.total_active_time_s,
                            "per_half_distance": v.per_half_distance,
                            "per_half_time": v.per_half_time,
                        }
                        for k, v in raw_profiles.items()
                    }
                    logger.info(f"Physical metrics computed for {len(physical_profiles)} players")
            except Exception as e:
                logger.warning(f"Physical metrics computation failed: {e}", exc_info=True)

        return MatchTrackData(
            match_id=0,
            fps=fps,
            total_frames=frame_number,
            duration_seconds=duration,
            frames=frames,
            track_registry=track_registry,
            player_teams=player_teams,
            tracking_metrics={
                "raw_tracks_detected": raw_tracks,
                "validated_player_tracks": len(valid_player_tracks),
                "fragmentation_rate": round(fragmentation_rate, 2),
                "expected_player_count": self.expected_player_count,
                "tracking_quality": quality,
                "frame_skip": frame_skip,
                "effective_fps": round(effective_fps, 1),
                "team_detection": team_detection_info,
                "mot_self_consistency": mot_metrics.get("mot_self_consistency"),
                "mot_details": mot_metrics,
                "stitched_tracks": len(stitch_map) if stitch_map else 0,
                "stitch_merge_map": {str(k): v for k, v in stitch_map.items()} if stitch_map else {},
                "tracking_metrics_merge_map": {str(k): v for k, v in tracking_merge_map.items()} if tracking_merge_map else {},
                "auto_homography": homography_matrix_auto,
                "physical_profiles": physical_profiles if physical_profiles else {},
                "ball_tracks": [
                    {"frame": b.frame, "timestamp": b.timestamp, "x": b.x, "y": b.y,
                     "conf": b.conf, "is_prediction": b.is_prediction, "radius": b.radius}
                    for b in ball_detections
                ] if ball_detections else [],
            },
            match_type=match_type,
            checkpoint_manager=ckpt_mgr,
        )

    @staticmethod
    def _detect_track_stitches(
        frames: list[FrameDetections],
        valid_player_tracks: set[int],
        track_first_frame: dict[int, int],
        track_last_frame: dict[int, int],
        fps: float,
        track_color_samples: dict[int, list],
        track_face_embeddings: dict[int, list] | None = None,
        track_reid_embeddings: dict[int, list] | None = None,
        spatial_threshold_px: float = 50.0,
        temporal_gap_max: float = 2.0,
    ) -> dict[int, int]:
        """Detect track fragments that belong to the same player.

        Uses four signals:
        1. Spatial overlap — overlapping frame windows with close x-centers
        2. Temporal gap — sequential tracks with matching boundary positions
        3. Team color — same dominant jersey color (when samples available)
        4. ReID embedding — cosine similarity of body appearance (when available)

        Merge modes:
        A. Spatial overlap (mode 1): overlapping frames + close x-centers
        B. Temporal gap (mode 2): sequential tracks, small gap, matching boundary
        C. Pure appearance (mode 3): strong ReID + color match, no spatial/temporal
           constraint — needed for broadcast cuts where the same player appears
           in different camera angles with large time gaps.

        Returns {discarded_track_id: survivor_track_id}.
        """
        if len(valid_player_tracks) < 2:
            return {}

        from collections import defaultdict
        track_centers: dict[int, dict[int, float]] = defaultdict(dict)
        for fdet in frames:
            fn = fdet.frame_number
            for det in fdet.detections:
                if det.class_name != "person" or det.track_id is None:
                    continue
                if det.track_id not in valid_player_tracks:
                    continue
                cx = (det.bbox[0] + det.bbox[2]) / 2
                track_centers[det.track_id][fn] = cx

        valid_list = sorted(valid_player_tracks)
        raw_map: dict[int, int] = {}

        def _identity_similar(tid_a: int, tid_b: int) -> bool:
            """Check if two tracks likely belong to the same player.

            Uses four signals: jersey color, face embedding (ArcFace),
            ReID embedding (OSNet), spatial overlap.
            Returns False only when at least two signals disagree.
            """
            signals = {"color": 0.0, "face": 0.0, "reid": 0.0}
            # Signal 1: jersey color
            sa = track_color_samples.get(tid_a, [])
            sb = track_color_samples.get(tid_b, [])
            if len(sa) >= 3 and len(sb) >= 3:
                avg_a = (int(np.mean([c[0] for c in sa])), int(np.mean([c[1] for c in sa])), int(np.mean([c[2] for c in sa])))
                avg_b = (int(np.mean([c[0] for c in sb])), int(np.mean([c[1] for c in sb])), int(np.mean([c[2] for c in sb])))
                color_dist = sum((a - b) ** 2 for a, b in zip(avg_a, avg_b)) ** 0.5
                signals["color"] = 1.0 if color_dist < 70 else -1.0
            # Signal 2: face embedding (ArcFace)
            if track_face_embeddings:
                fa = track_face_embeddings.get(tid_a, [])
                fb = track_face_embeddings.get(tid_b, [])
                if len(fa) >= 1 and len(fb) >= 1:
                    avg_a = np.mean(fa, axis=0)
                    avg_b = np.mean(fb, axis=0)
                    avg_a /= max(np.linalg.norm(avg_a), 1e-8)
                    avg_b /= max(np.linalg.norm(avg_b), 1e-8)
                    face_dist = float(np.linalg.norm(avg_a - avg_b))
                    signals["face"] = 1.0 if face_dist < 0.6 else -1.0
            # Signal 3: ReID body embedding (OSNet / SoccerNet)
            if track_reid_embeddings:
                ra = track_reid_embeddings.get(tid_a, [])
                rb = track_reid_embeddings.get(tid_b, [])
                if len(ra) >= 1 and len(rb) >= 1:
                    avg_a = np.mean(ra, axis=0)
                    avg_b = np.mean(rb, axis=0)
                    norm_a = max(np.linalg.norm(avg_a), 1e-8)
                    norm_b = max(np.linalg.norm(avg_b), 1e-8)
                    reid_sim = float(np.dot(avg_a, avg_b) / (norm_a * norm_b))
                    signals["reid"] = 1.0 if reid_sim > 0.6 else -1.0
            scores = [v for v in signals.values() if v != 0.0]
            if not scores:
                return True  # no signals → don't penalize
            return sum(scores) > 0  # majority vote

        for i in range(len(valid_list)):
            tid_a = valid_list[i]
            if tid_a in raw_map:
                continue
            frames_a = set(track_centers.get(tid_a, {}).keys())
            if not frames_a:
                continue

            for j in range(i + 1, len(valid_list)):
                tid_b = valid_list[j]
                if tid_b in raw_map:
                    continue
                frames_b = set(track_centers.get(tid_b, {}).keys())
                if not frames_b:
                    continue

                if not _identity_similar(tid_a, tid_b):
                    continue

                overlap = frames_a & frames_b
                if overlap:
                    close = sum(
                        1 for fn in overlap
                        if abs(track_centers[tid_a][fn] - track_centers[tid_b][fn]) < spatial_threshold_px
                    )
                    if close / len(overlap) > 0.3:
                        survivor = tid_a if len(frames_a) >= len(frames_b) else tid_b
                        discarded = tid_b if survivor == tid_a else tid_a
                        raw_map[discarded] = survivor
                else:
                    first_a, last_a = min(frames_a), max(frames_a)
                    first_b, last_b = min(frames_b), max(frames_b)
                    if first_b > last_a:
                        gap = (first_b - last_a) / fps
                        if 0 < gap <= temporal_gap_max:
                            ca = track_centers[tid_a].get(last_a)
                            cb = track_centers[tid_b].get(first_b)
                            if ca is not None and cb is not None and abs(ca - cb) < spatial_threshold_px * 1.5:
                                survivor = tid_a if len(frames_a) >= len(frames_b) else tid_b
                                discarded = tid_b if survivor == tid_a else tid_a
                                raw_map[discarded] = survivor
                    elif first_a > last_b:
                        gap = (first_a - last_b) / fps
                        if 0 < gap <= temporal_gap_max:
                            ca = track_centers[tid_b].get(last_b)
                            cb = track_centers[tid_a].get(first_a)
                            if ca is not None and cb is not None and abs(ca - cb) < spatial_threshold_px * 1.5:
                                survivor = tid_a if len(frames_a) >= len(frames_b) else tid_b
                                discarded = tid_b if survivor == tid_a else tid_a
                                raw_map[discarded] = survivor

                # Mode C: Pure appearance match — broadcast cross-camera re-identification.
                ra_pure = track_reid_embeddings.get(tid_a, []) if track_reid_embeddings else []
                rb_pure = track_reid_embeddings.get(tid_b, []) if track_reid_embeddings else []
                if len(ra_pure) >= 1 and len(rb_pure) >= 1:
                    avg_a = np.mean(ra_pure, axis=0)
                    avg_b = np.mean(rb_pure, axis=0)
                    reid_sim = float(np.dot(avg_a, avg_b) / (
                        max(np.linalg.norm(avg_a), 1e-8) * max(np.linalg.norm(avg_b), 1e-8)
                    ))
                    sa = track_color_samples.get(tid_a, [])
                    sb = track_color_samples.get(tid_b, [])
                    color_ok = len(sa) >= 1 and len(sb) >= 1
                    if color_ok:
                        avg_a_c = (
                            int(np.mean([c[0] for c in sa])),
                            int(np.mean([c[1] for c in sa])),
                            int(np.mean([c[2] for c in sa])),
                        )
                        avg_b_c = (
                            int(np.mean([c[0] for c in sb])),
                            int(np.mean([c[1] for c in sb])),
                            int(np.mean([c[2] for c in sb])),
                        )
                        color_dist = sum((a - b) ** 2 for a, b in zip(avg_a_c, avg_b_c)) ** 0.5
                    else:
                        color_dist = 999.0
                    # Adaptive threshold: tracks with few embeddings need higher confidence
                    reid_thresh = 0.70 if (len(ra_pure) <= 2 or len(rb_pure) <= 2) else 0.65
                    color_thresh = 70 if (len(sa) <= 3 or len(sb) <= 3) else 55
                    if reid_sim > reid_thresh and color_dist < color_thresh:
                        if tid_a not in raw_map and tid_b not in raw_map:
                            survivor = tid_a if len(frames_a) >= len(frames_b) else tid_b
                            discarded = tid_b if survivor == tid_a else tid_a
                            raw_map[discarded] = survivor

        # Resolve transitive entries (e.g. 2→1, 3→2 ⇒ 3→1)
        resolved: dict[int, int] = {}
        for discarded, survivor in raw_map.items():
            cur = survivor
            while cur in raw_map:
                cur = raw_map[cur]
            resolved[discarded] = cur
        return resolved

    @staticmethod
    def _bbox_iou(bbox_a: tuple[float, float, float, float],
                  bbox_b: tuple[float, float, float, float]) -> float:
        """Compute IoU between two bounding boxes (x1, y1, x2, y2)."""
        x1 = max(bbox_a[0], bbox_b[0])
        y1 = max(bbox_a[1], bbox_b[1])
        x2 = min(bbox_a[2], bbox_b[2])
        y2 = min(bbox_a[3], bbox_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
        area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def _compute_pitch_mask(self, frame):
        """Compute binary mask of pitch area using adaptive HSV color detection.

        Auto-calibrates pitch color range from the first frame using histogram
        peak detection on the H channel. Falls back to hardcoded range if
        auto-detection produces an empty mask.
        """
        try:
            import cv2
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            if not hasattr(self, "_pitch_hsv_range") or self._pitch_hsv_range is None:
                h_channel = hsv[:, :, 0]
                hist = cv2.calcHist([h_channel], [0], None, [180], [0, 180])
                hist_smooth = cv2.GaussianBlur(hist, (5, 5), 0)
                peak_idx = int(np.argmax(hist_smooth))
                margin = 15
                lower_h = max(0, peak_idx - margin)
                upper_h = min(180, peak_idx + margin)
                self._pitch_hsv_range = (
                    np.array([lower_h, 30, 30]),
                    np.array([upper_h, 255, 255]),
                )
                logger.info(f"Auto-detected pitch HSV range: H=[{lower_h}, {upper_h}]")
            lower_green, upper_green = self._pitch_hsv_range
            mask = cv2.inRange(hsv, lower_green, upper_green)
            pitch_pixels = cv2.countNonZero(mask)
            if pitch_pixels < frame.shape[0] * frame.shape[1] * 0.05:
                lower_green = np.array([25, 40, 40])
                upper_green = np.array([90, 255, 255])
                mask = cv2.inRange(hsv, lower_green, upper_green)
                logger.warning("Pitch mask too small, falling back to hardcoded range")
            kernel = np.ones((15, 15), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None
            largest = max(contours, key=cv2.contourArea)
            filled = np.zeros_like(mask)
            cv2.drawContours(filled, [largest], -1, 255, -1)
            return filled > 0
        except Exception:
            return None

    def _assess_tracking_quality(
        self, fragmentation_rate: float, count_ratio: float = 1.0
    ) -> str:
        """Assess tracking quality based on count ratio (closer to 1.0 = better)."""
        if 0.8 <= count_ratio <= 1.3:
            return "excellent"
        elif count_ratio <= 1.5:
            return "good"
        elif count_ratio <= 2.0:
            return "fair"
        elif count_ratio <= 3.0:
            return "poor"
        else:
            return "very_poor"

    async def shutdown(self) -> None:
        """Release resources."""
        self._model = None
        self._initialized = False
        logger.info("CVService shutdown")

    async def detect_jersey_numbers(
        self,
        video_path: Path,
        track_id_jersey_map: dict[int, int] | None = None,
        sample_every_n_frames: int = 30,
    ) -> dict[int, dict]:
        """Detect jersey numbers for tracked players.

        Uses a combination of:
        1. Torso region detection (top 1/3 of bounding box)
        2. OCR on the torso region
        3. Temporal voting across frames (most common number wins)

        Args:
            video_path: Path to video file
            track_id_jersey_map: Optional map to pre-fill known jerseys
            sample_every_n_frames: Sample every N frames (default 30 = 1/sec at 30fps)

        Returns:
            Dict mapping track_id -> {"jersey_number": int, "confidence": float, "candidates": dict}
        """
        import cv2

        if not self._initialized:
            await self.initialize()

        if track_id_jersey_map is None:
            track_id_jersey_map = {}

        track_jersey_votes: dict[int, dict[int, int]] = {}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video for jersey detection: {video_path}")
            return {}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = 0

        from kawkab.services.jersey_service import JerseyNumberService

        jersey_svc = JerseyNumberService(gpu_enabled=self.gpu_enabled)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % sample_every_n_frames == 0:
                    results = self._model.track(
                        frame,
                        persist=True,
                        conf=self.confidence_threshold,
                        classes=[0],
                        verbose=False,
                    )
                    if results and len(results) > 0:
                        boxes = results[0].boxes
                        if boxes is not None and len(boxes) > 0:
                            for i in range(len(boxes)):
                                if boxes.id is None:
                                    continue
                                track_id = int(boxes.id[i].cpu().numpy())
                                bbox = boxes.xyxy[i].cpu().numpy()
                                x1, y1, x2, y2 = map(int, bbox)

                                torso_y1 = y1 + int((y2 - y1) * 0.2)
                                torso_y2 = y1 + int((y2 - y1) * 0.6)
                                torso_x1 = x1 + int((x2 - x1) * 0.1)
                                torso_x2 = x2 - int((x2 - x1) * 0.1)

                                torso_y1 = max(0, torso_y1)
                                torso_y2 = min(frame.shape[0], torso_y2)
                                torso_x1 = max(0, torso_x1)
                                torso_x2 = min(frame.shape[1], torso_x2)

                                if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
                                    continue

                                torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
                                result = jersey_svc.detect(torso)
                                if result["jersey_number"] is not None:
                                    num = result["jersey_number"]
                                    if track_id not in track_jersey_votes:
                                        track_jersey_votes[track_id] = {}
                                    track_jersey_votes[track_id][num] = (
                                        track_jersey_votes[track_id].get(num, 0) + 1
                                    )

                frame_count += 1
                if frame_count % (sample_every_n_frames * 30) == 0:
                    pct = (frame_count / total_frames) * 100
                    logger.debug(f"Jersey OCR: {pct:.0f}% ({frame_count}/{total_frames})")
        finally:
            cap.release()

        results: dict[int, dict] = {}
        for track_id, votes in track_jersey_votes.items():
            if not votes:
                continue
            total_votes = sum(votes.values())
            best_number = max(votes.items(), key=lambda x: x[1])
            confidence = best_number[1] / total_votes if total_votes > 0 else 0

            if track_id in track_id_jersey_map:
                results[track_id] = {
                    "jersey_number": track_id_jersey_map[track_id],
                    "confidence": 1.0,
                    "candidates": {track_id_jersey_map[track_id]: 1},
                    "source": "manual",
                }
            else:
                results[track_id] = {
                    "jersey_number": best_number[0],
                    "confidence": round(confidence, 2),
                    "candidates": dict(sorted(votes.items(), key=lambda x: -x[1])[:5]),
                    "source": "ocr",
                }

        logger.info(
            f"Jersey detection complete: {len(results)} players, "
            f"avg confidence: {sum(r['confidence'] for r in results.values()) / max(1, len(results)):.1%}"
        )
        return results

    def _estimate_jersey_from_pixels(
        self, white_pixels: int, width: int, height: int
    ) -> int | None:
        """Fallback: estimate jersey number from white pixel count (rough heuristic)."""
        ratio = white_pixels / (width * height) if (width * height) > 0 else 0
        if ratio < 0.05:
            return None
        estimated = int(1 + (ratio * 100) % 99)
        if 0 < estimated < 100:
            return estimated
        return None
    async def detect_team_colors(
        self,
        video_path: Path,
        sample_frames: int = 20,
        known_track_ids: set[int] | None = None,
    ) -> dict[int, dict]:
        """Detect dominant jersey color for each tracked player."""
        import cv2

        if not self._initialized:
            await self.initialize()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_positions = [
            int(i * (total_frames - 1) / max(1, sample_frames - 1))
            for i in range(sample_frames)
        ]

        track_colors = defaultdict(list)

        for target_frame in frame_positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if not ret:
                continue

            results = self._model.track(
                frame, persist=True, conf=self.confidence_threshold,
                classes=[0], verbose=False,
            )
            if not results or len(results) == 0:
                continue
            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                if boxes.id is None:
                    continue
                track_id = int(boxes.id[i].cpu().numpy())
                if known_track_ids is not None and track_id not in known_track_ids:
                    continue
                bbox = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = map(int, bbox)
                torso_y1 = max(0, y1 + int((y2 - y1) * 0.25))
                torso_y2 = min(frame.shape[0], y1 + int((y2 - y1) * 0.55))
                torso_x1 = max(0, x1 + int((x2 - x1) * 0.2))
                torso_x2 = min(frame.shape[1], x2 - int((x2 - x1) * 0.2))
                if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
                    continue
                torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
                if torso.size == 0:
                    continue
                avg_color = self._get_dominant_color(torso)
                if avg_color:
                    track_colors[track_id].append(avg_color)

        cap.release()

        result = {}
        for tid, colors in track_colors.items():
            if len(colors) < 3:
                continue
            avg = (
                int(np.mean([c[0] for c in colors])),
                int(np.mean([c[1] for c in colors])),
                int(np.mean([c[2] for c in colors])),
            )
            result[tid] = {
                "primary_color": avg,
                "color_hex": f"#{avg[2]:02x}{avg[1]:02x}{avg[0]:02x}",
                "samples": len(colors),
            }

        clusters = self._cluster_team_colors(result, n_clusters=3)
        for tid, label in clusters.items():
            if tid in result:
                result[tid]["team_label"] = label

        n_teams = len(set(clusters.values()))
        logger.info(f"Team color detection: {len(result)} players, {n_teams} clusters")
        return result

    def _extract_torso(self, frame: np.ndarray, bbox: tuple) -> np.ndarray | None:
        """Extract torso region from frame using bbox (x1,y1,x2,y2).

        Returns the upper-middle portion of the bbox (jersey area).
        """
        if frame is None or frame.size == 0:
            return None
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        torso_y1 = max(0, y1 + int((y2 - y1) * 0.25))
        torso_y2 = min(h, y1 + int((y2 - y1) * 0.55))
        torso_x1 = max(0, x1 + int((x2 - x1) * 0.2))
        torso_x2 = min(w, x2 - int((x2 - x1) * 0.2))
        if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
            return None
        torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
        if torso.size == 0:
            return None
        return torso

    def _get_dominant_color(self, img_region):
        """Get dominant non-white, non-black color from a region (BGR)."""
        if img_region.size == 0:
            return None
        h, w = img_region.shape[:2]
        if h < 5 or w < 5:
            return None
        pixels = img_region.reshape(-1, 3)
        mask = ~((pixels[:, 0] > 230) & (pixels[:, 1] > 230) & (pixels[:, 2] > 230))
        pixels = pixels[mask]
        mask2 = ~((pixels[:, 0] < 30) & (pixels[:, 1] < 30) & (pixels[:, 2] < 30))
        pixels = pixels[mask2]
        if len(pixels) < 5:
            return None
        return (
            int(np.mean(pixels[:, 0])),
            int(np.mean(pixels[:, 1])),
            int(np.mean(pixels[:, 2])),
        )

    def _cluster_team_colors(self, color_data, n_clusters=2):
        """Cluster players into teams based on jersey color.

        Supports auto-detection of referee (n_clusters=3):
        cluster with darkest/saturation-lowest hue → referee.
        """
        if len(color_data) < 2:
            return {tid: 0 for tid in color_data}

        tids = list(color_data.keys())
        colors_bgr = np.array([color_data[tid]["primary_color"] for tid in tids])

        auto_detect_ref = n_clusters >= 3
        actual_n = min(n_clusters if not auto_detect_ref else 3, len(tids))

        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=actual_n, random_state=42, n_init=10)
            labels = kmeans.fit_predict(colors_bgr)
            label_map: dict[int, str] = {}

            if actual_n >= 3:
                centroids_bgr = kmeans.cluster_centers_.astype(int)
                import cv2
                centroids_hsv = [
                    cv2.cvtColor(
                        np.uint8([[c]]), cv2.COLOR_BGR2HSV
                    )[0, 0]
                    for c in centroids_bgr
                ]
                ref_idx = min(
                    range(len(centroids_hsv)),
                    key=lambda i: (
                        centroids_hsv[i][1],
                        -float(abs(centroids_hsv[i][0])),
                    ),
                )
                team_indices = [i for i in range(actual_n) if i != ref_idx]
                sorted_teams = sorted(
                    team_indices,
                    key=lambda i: sum(centroids_bgr[i]),
                    reverse=True,
                )
                label_map[ref_idx] = "referee"
                label_map[sorted_teams[0]] = "home"
                label_map[sorted_teams[1]] = "away"
            else:
                sorted_idx = sorted(
                    range(actual_n),
                    key=lambda i: sum(kmeans.cluster_centers_[i].astype(int)),
                    reverse=True,
                )
                label_map[sorted_idx[0]] = "home"
                label_map[sorted_idx[1]] = "away"

            return {tids[i]: label_map.get(int(labels[i]), str(int(labels[i]))) for i in range(len(tids))}
        except ImportError:
            sorted_by_color = sorted(
                tids, key=lambda t: sum(color_data[t]["primary_color"])
            )
            result = {}
            for i, tid in enumerate(sorted_by_color):
                result[tid] = "home" if i < len(sorted_by_color) / 2 else "away"
            return result
