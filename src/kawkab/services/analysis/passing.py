"""Passing analysis mixin."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class PassingMixin:
    def _compute_pass_network(self, events):
        edges: dict[tuple[int, int], int] = defaultdict(int)

        for event in events:
            if event["type"] != "pass" or not event.get("completed"):
                continue
            edge = (event["from_track_id"], event["to_track_id"])
            edges[edge] += 1

        nodes = set()
        for (src, dst) in edges:
            nodes.add(src)
            nodes.add(dst)

        return {
            "nodes": [{"id": n} for n in nodes],
            "edges": [
                {"source": s, "target": t, "weight": w}
                for (s, t), w in edges.items()
            ],
        }

    def detect_line_breaking_passes(self, events, n_lines=3):
        plen = self.pitch_length
        line_breaks = []
        line_positions = [plen * i / (n_lines + 1) for i in range(1, n_lines + 1)]
        for event in events:
            if event.get("type") != "pass":
                continue
            if not event.get("completed", False):
                continue
            metadata = event.get("metadata", {})
            start_x = metadata.get("start_x_pct", 0.5) * plen
            end_x = metadata.get("end_x_pct", 0.6) * plen
            if end_x <= start_x:
                continue
            lines_crossed = 0
            for line_x in line_positions:
                if start_x < line_x <= end_x:
                    lines_crossed += 1
            if lines_crossed >= 2:
                line_breaks.append({
                    "team": event.get("team", "home"),
                    "player_track_id": event.get("player_track_id"),
                    "start_x_pct": round(metadata.get("start_x_pct", 0.5), 3),
                    "end_x_pct": round(metadata.get("end_x_pct", 0.6), 3),
                    "lines_crossed": lines_crossed,
                    "vertical_gain_pct": round(end_x / plen - start_x / plen, 3),
                })
        return line_breaks

    def attribute_possession_robust(self, events, frames=None):
        last_known: dict[str, int | None] = {"home": None, "away": None}
        attributed = []
        for event in events:
            team = event.get("team", "home")
            track_id = event.get("player_track_id")
            if track_id is not None:
                last_known[team] = track_id
                attributed.append({**event, "attribution_source": "explicit"})
                continue
            inferred = last_known.get(team)
            if inferred is not None:
                attributed.append({
                    **event,
                    "player_track_id": inferred,
                    "attribution_source": "last_known",
                })
            else:
                attributed.append({
                    **event,
                    "player_track_id": -1,
                    "attribution_source": "unknown",
                })
        return attributed
