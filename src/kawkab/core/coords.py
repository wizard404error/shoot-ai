from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PitchConfig:
    length_m: float = 105.0
    width_m: float = 68.0

    @property
    def half_length(self) -> float:
        return self.length_m / 2.0

    @property
    def half_width(self) -> float:
        return self.width_m / 2.0

    @property
    def diagonal_m(self) -> float:
        return (self.length_m**2 + self.width_m**2) ** 0.5

    def third_x(self, which: str = "def") -> float:
        if which == "def":
            return self.length_m / 3.0
        elif which == "att":
            return self.length_m * 2.0 / 3.0
        return self.length_m / 2.0


STANDARD_PITCH = PitchConfig()

FINAL_THIRD_X = STANDARD_PITCH.length_m * 2.0 / 3.0


def is_normalized(val: float) -> bool:
    return 0.0 <= val <= 1.5


def norm_to_meters(val: float, pitch_dim: float) -> float:
    if is_normalized(val):
        return val * pitch_dim
    return val


def clamp_pitch(x: float, y: float, pitch: PitchConfig = STANDARD_PITCH) -> tuple[float, float]:
    return max(0.0, min(pitch.length_m, x)), max(0.0, min(pitch.width_m, y))


def pitch_third(x: float, pitch: PitchConfig = STANDARD_PITCH) -> str:
    if x < pitch.third_x("def"):
        return "defensive"
    elif x > pitch.third_x("att"):
        return "attacking"
    return "middle"


def half_space(x: float, y: float, pitch: PitchConfig = STANDARD_PITCH) -> str:
    central = pitch.width_m * 0.4
    if central < y < pitch.width_m - central:
        return "central"
    hw = pitch.width_m / 2.0
    if y < hw:
        return "left_halfspace"
    return "right_halfspace"


def zone_label(x: float, y: float, pitch: PitchConfig = STANDARD_PITCH) -> str:
    third = pitch_third(x, pitch)
    hspace = half_space(x, y, pitch)
    if hspace == "central":
        return f"{third}_central"
    side = "left" if y < pitch.width_m / 2 else "right"
    return f"{third}_{side}"


def euclidean_distance_m(
    x1: float, y1: float, x2: float, y2: float, pitch: PitchConfig = STANDARD_PITCH
) -> float:
    x1m = norm_to_meters(x1, pitch.length_m)
    x2m = norm_to_meters(x2, pitch.length_m)
    y1m = norm_to_meters(y1, pitch.width_m)
    y2m = norm_to_meters(y2, pitch.width_m)
    return ((x2m - x1m) ** 2 + (y2m - y1m) ** 2) ** 0.5


def meters_to_pixel_fraction(
    meters: float, pitch: PitchConfig = STANDARD_PITCH, view_width_px: float = 1280.0
) -> float:
    return meters / pitch.length_m * view_width_px
