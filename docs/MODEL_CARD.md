# Model Card — Kawkab AI

## Models in Use

### YOLOv11 (n/s/m/l/x)

| Property | Value |
|---|---|
| **Task** | Object detection (person, sports ball) |
| **Architecture** | Ultralytics YOLOv11 (CSPDarknet + PAN neck) |
| **Weights** | `yolo11{n/s/m/l/x}.pt` from ultralytics assets |
| **Training data** | COCO 2017 (118k images, 80 classes, includes "person") |
| **Fine-tuning** | None — used as-is from ultralytics |
| **Input** | BGR image (variable resolution, auto-scaled by YOLO) |
| **Output** | Bounding boxes + class labels + confidence scores |
| **Classes used** | `0` (person), `32` (sports ball) |
| **Confidence threshold** | Person: 0.4, Ball: 0.15 |
| **Failure modes** | Occluded players, distant players (<40px tall), overlapping kits, unusual camera angles, extreme lighting |

### OSNet SportsMOT (boxmot)

| Property | Value |
|---|---|
| **Task** | Person ReID embedding |
| **Architecture** | OSNet (Omni-Scale Network) |
| **Weights** | `osnet_sportsmot.pt` from boxmot v3.0.0 |
| **Training data** | SportsMOT (multi-sport tracking dataset) |
| **Output** | 512-d L2-normalized embedding vector |
| **Used in** | boxmot BoT-SORT tracker (GPU tier medium+) and Norfair fallback |
| **Failure modes** | Same-kit players on same team, extreme motion blur, very low resolution crops |

### SoccerNet ReID (optional)

| Property | Value |
|---|---|
| **Task** | Football-specific person ReID embedding |
| **Architecture** | ResNet-50 + CircleLoss |
| **Weights** | `soccernet_reid.pt` (200 MB) from SoccerNet tracking |
| **Training data** | SoccerNet tracking dataset (football matches) |
| **Output** | 512-d L2-normalized embedding vector |
| **Used in** | Norfair tracker (fallback after OSNet) |
| **Status** | Optional dependency (`pip install kawkab[reid]`) |

### ArcFace (face recognition)

| Property | Value |
|---|---|
| **Task** | Face embedding for cross-cut identity verification |
| **Architecture** | InsightFace ArcFace (ResNet-100 backbone) |
| **Training data** | MS1M-V2 (5.8M faces, 85k identities) |
| **Output** | 512-d normalized embedding |
| **Used in** | Post-hoc track stitching (A1), sampled every 2s |
| **Failure modes** | Players facing away, distant faces (<30px), low light, occlusion by other players |

## Model Selection Logic

```
GPU tier "ultra" → YOLO11x + boxmot BoT-SORT (OSNet)
GPU tier "high"  → YOLO11l + boxmot BoT-SORT (OSNet)
GPU tier "medium" → YOLO11m + boxmot BoT-SORT (OSNet)
GPU tier "low"   → YOLO11s + Norfair (HSV ReID)
Fallback (no GPU) → YOLO11n + Ultralytics built-in tracker
```

Benchmark cache overrides static tier mapping. After one successful benchmark run per GPU tier, the best measured variant is used instead of the heuristic.

## Known Limitations

1. **YOLO "ball" class** is COCO's sports ball — on amateur footage it frequently misses the ball or misclassifies small objects as ball. Ball tracking is less reliable than person tracking.
2. **No team-specific training** — all weights are generic (COCO, SportsMOT). Football-specific fine-tuning would improve detection of players in match kits vs. warm-up kits.
3. **No occlusion model** — when two players overlap, one track may drop or IDs may swap. The track stitching module recovers some of these post-hoc.
4. **ReID fails on identical kits** — teammates wearing the same kit can only be distinguished by face (sparse) or spatial position (breaks down at half-time formation reset).
5. **Homography depends on pitch lines** — if the pitch has no visible lines (muddy field, snow, unusual markings), auto-calibration will fail and the analysis will run in pixel space.
