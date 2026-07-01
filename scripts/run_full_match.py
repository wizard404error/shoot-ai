"""Run France vs Sweden 15-min segment pipeline validation."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)

FRANCE_SWEDEN_15 = Path(__file__).resolve().parent.parent / "france_sweden_15min.mp4"
FRANCE_SWEDEN_FULL = Path(__file__).resolve().parent.parent / "France vs Sweden.mp4"


async def run(video_path: Path, frame_skip: int = 6):
    from kawkab.services.cv_service import CVService

    print(f"=== Processing {video_path.name} ===")
    print(f"Resolution: checking...")
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    eff_fps = fps / (frame_skip + 1)
    print(f"Frames: {frames}, FPS: {fps}, Resolution: {w}x{h}")
    print(f"Frame skip: {frame_skip}, Effective FPS: {eff_fps:.1f}")
    print(f"Estimated processing time: {frames / eff_fps / 60:.0f} min at 1x")

    svc = CVService(model_size="m", gpu_enabled=True)
    await svc.initialize()

    match_data = await svc.process_video(
        video_path, frame_skip=frame_skip, enable_team_detection=True,
    )

    metrics = match_data.tracking_metrics

    print()
    print("=== RESULTS ===")
    print(f"Raw tracks detected: {metrics.get('raw_tracks_detected')}")
    print(f"Validated player tracks: {metrics.get('validated_player_tracks')}")
    print(f"Fragmentation rate: {metrics.get('fragmentation_rate')}x")
    print(f"Tracking quality: {metrics.get('tracking_quality')}")
    print(f"Stitched tracks: {metrics.get('stitched_tracks')}")
    print(f"Stitch merges: {len(metrics.get('stitch_merge_map', {}))}")

    td = metrics.get("team_detection", {})
    if td:
        print(f"Team detection: home={td.get('home_size')}, away={td.get('away_size')}, ref={td.get('ref_size')}")

    auto_h = metrics.get("auto_homography")
    print(f"Auto-calibration: {'yes' if auto_h else 'no'}")

    print()
    print(f"Match type: {match_data.match_type}")
    print(f"Duration: {match_data.duration_seconds:.0f}s ({match_data.duration_seconds/60:.1f} min)")
    print(f"Sampled frames: {len(match_data.frames)}")

    await svc.shutdown()
    print("=== Done ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run pipeline on France vs Sweden match")
    parser.add_argument("--skip", type=int, default=6, help="Frame skip rate (default: 6)")
    parser.add_argument("--full", action="store_true", help="Process full match instead of 15-min segment")
    args = parser.parse_args()

    video = FRANCE_SWEDEN_FULL if args.full else FRANCE_SWEDEN_15
    asyncio.run(run(video, frame_skip=args.skip))
