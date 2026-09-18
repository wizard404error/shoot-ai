"""GUI e2e: broad slot-dispatch audit through the real booted app (C1 follow-up).

The v0.13.1 split shipped handlers whose unit tests all passed while the
features were dead in the real app (missing awaits, key-shape mismatches,
a wrong validator, a missing ctor arg, a self-reading lazy property).
That pass fixed the GPS/xA/pressing/setpiece surface; this module extends
the same real-dispatch contract across the remaining handler clusters.

Contract per cluster: boot the real MainWindow (services constructed,
storage initialized exactly as a user session starts), dispatch the
cluster's slots through the bridge with production-shaped arguments, and
assert the app answers with parseable JSON carrying the fields the UI
renders. Slots backed by optional heavy engines (MuJoCo, FluidX3D, cloud
logins) must return an honest error payload, never garbage or a hang.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest

pyside6 = pytest.importorskip("PySide6")


@pytest.fixture()
def qapp(monkeypatch, tmp_path):
    """Offscreen QApplication with an isolated environment.

    Same isolation contract as the other GUI e2e modules (duplicated here:
    tests/ has no __init__.py, so the fixture cannot be imported).
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_DOCUMENTS_DIR", str(tmp_path / "xdg-docs"))
    monkeypatch.setenv("KAWKAB_DEBUG", "false")
    monkeypatch.delenv("KAWKAB_DB_URL", raising=False)

    import kawkab.core.paths as paths_mod

    if hasattr(paths_mod, "_paths"):
        monkeypatch.setattr(paths_mod, "_paths", None)
    from kawkab.core.config import get_settings

    get_settings.cache_clear()

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["kawkab-slot-audit"])
    yield app
    get_settings.cache_clear()


def dispatch(window, name, *args):
    """Await whatever the bridge slot returns (PySide6 allows both)."""
    out = getattr(window.bridge, name)(*args)
    if inspect.isawaitable(out):
        out = asyncio.run(out) if not _in_loop() else out
    return out


def _in_loop():
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


async def adispatch(window, name, *args):
    out = getattr(window.bridge, name)(*args)
    if inspect.isawaitable(out):
        out = await out
    return out


def seed_match(window, name: str = "audit fixture") -> int:
    """Seed a match + players + events through the production API."""

    async def main():
        storage = window.storage
        await storage.initialize()
        mid = await storage.save_match(name, "audit.mp4", "Reds", "Blues")
        await storage.save_player(
            mid, {"track_id": 5, "name": "P5", "team": "Reds", "jersey_number": 5}
        )
        await storage.save_player(
            mid, {"track_id": 6, "name": "P6", "team": "Reds", "jersey_number": 6}
        )
        events = []
        for i, (team, x) in enumerate(
            [("home", 20), ("home", 50), ("home", 80), ("away", 30), ("away", 60)]
        ):
            events.append(
                {
                    "type": "pass",
                    "timestamp": float(i),
                    "team": team,
                    "completed": True,
                    "from_track_id": 5,
                    "to_track_id": 6,
                    "x": float(x),
                    "y": 34.0,
                    "end_x": float(x + 10),
                    "end_y": 30.0,
                }
            )
        events += [
            {
                "type": "shot",
                "timestamp": 10.0,
                "team": "home",
                "from_track_id": 5,
                "x": 95.0,
                "y": 34.0,
                "completed": True,
                "metadata": {"xg": 0.3},
            },
            {
                "type": "tackle",
                "timestamp": 11.0,
                "team": "away",
                "from_track_id": 6,
                "x": 40.0,
                "y": 30.0,
            },
            {
                "type": "goal",
                "timestamp": 12.0,
                "team": "home",
                "from_track_id": 5,
                "x": 99.0,
                "y": 34.0,
            },
        ]
        await storage.save_events_bulk(mid, events)
        return mid

    return asyncio.run(main())


def _assert_ok(payload: str, slot: str, *, allow_error: bool = False):
    d = json.loads(payload)
    if allow_error:
        assert isinstance(d, dict), f"{slot}: non-dict payload {str(d)[:80]}"
        return d
    assert not (isinstance(d, dict) and "error" in d), f"{slot} errored: {str(d)[:200]}"
    return d


def _reset_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DOCUMENTS_DIR", str(tmp_path / "xdg-docs"))
    monkeypatch.setenv("HOME", str(tmp_path))
    import kawkab.core.paths as paths_mod

    if hasattr(paths_mod, "_paths"):
        monkeypatch.setattr(paths_mod, "_paths", None)
    # get_settings caches env-derived values at first call; without this
    # clear the appdata dir resolves from a previous test's env and user
    # data (opponent profiles, scouting network) leaks into it.
    from kawkab.core.config import get_settings

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# match_intel: all 17 slots through the real bridge
# ---------------------------------------------------------------------------


def test_match_intel_all_slots_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        mid = seed_match(window, "match-intel audit")
        m = str(mid)

        async def main():
            results = {}
            simple = [
                "analyze_build_up",
                "analyze_finishing",
                "compute_goals_added",
                "compute_phase_xg",
                "compute_territory_value",
                "generate_match_report",
                "get_dominance_index",
                "get_match_quality_score",
                "get_pitch_control_overlay",
                "get_space_control_heatmap",
            ]
            for name in simple:
                results[name] = await adispatch(window, name, m)
            results["estimate_transfer_fee"] = await adispatch(
                window, "estimate_transfer_fee", m, "5"
            )
            results["get_player_pass_sonar"] = await adispatch(
                window, "get_player_pass_sonar", m, "5"
            )
            results["get_player_role"] = await adispatch(window, "get_player_role", m, "5")
            results["generate_game_plan"] = await adispatch(window, "generate_game_plan", m, m)
            results["simulate_league"] = await adispatch(window, "simulate_league", m, "3")
            results["get_xa_report"] = await adispatch(window, "get_xa_report", m)
            results["get_pressing_report"] = await adispatch(window, "get_pressing_report", m)
            return results

        results = asyncio.run(main())
        for slot, payload in results.items():
            _assert_ok(payload, slot)

        # value-level pins on three slots with known seeded truth
        sonar = json.loads(results["get_player_pass_sonar"])
        assert sonar["total_passes"] == 5, sonar
        xa = json.loads(results["get_xa_report"])
        assert xa["home"] > 0 and xa["away"] > 0, xa
        pressing = json.loads(results["get_pressing_report"])
        assert pressing["home"]["traps"] >= 0 and "shots_from_traps" in pressing["home"]
    finally:
        window.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# coding: full CRUD round trip through the real bridge
# ---------------------------------------------------------------------------


def test_coding_cluster_round_trip_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        mid = seed_match(window, "coding audit")

        async def main():
            out = {}
            out["save"] = await adispatch(
                window,
                "save_coding_tag",
                str(mid),
                json.dumps(
                    {
                        "event_type": "shot",
                        "timestamp": 5.0,
                        "team": "home",
                        "player_track_id": 5,
                        "notes": "audit",
                    }
                ),
            )
            saved = json.loads(out["save"])
            out["list"] = await adispatch(window, "get_coding_tags", str(mid))
            out["stats"] = await adispatch(window, "get_coding_tag_stats", str(mid))
            out["players"] = await adispatch(window, "get_coding_players", str(mid))
            out["by_player"] = await adispatch(window, "get_coding_tags_by_player", str(mid), "5")
            out["by_type"] = await adispatch(window, "get_coding_tags_by_type", str(mid), "shot")
            out["templates"] = await adispatch(window, "get_coding_templates")
            tid = saved.get("tag_id")
            if tid:
                out["update"] = await adispatch(
                    window, "update_coding_tag", str(tid), json.dumps({"notes": "edited"})
                )
                out["delete"] = await adispatch(window, "delete_coding_tag", str(tid))
            return out

        out = asyncio.run(main())
        saved = json.loads(out["save"])
        assert saved.get("success") is True and saved.get("tag_id", 0) > 0, saved
        for slot in ("list", "stats", "players", "by_player", "by_type", "templates"):
            _assert_ok(out[slot], slot)
        if "update" in out:
            _assert_ok(out["update"], "update_coding_tag")
            _assert_ok(out["delete"], "delete_coding_tag")
    finally:
        window.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# whiteboard: full authoring lifecycle through the real bridge
# ---------------------------------------------------------------------------


def test_whiteboard_lifecycle_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        created = json.loads(dispatch(window, "whiteboard_create", "audit board", "4-3-3"))
        sid = created.get("id") or created.get("state_id")
        assert sid, created

        got = _assert_ok(dispatch(window, "whiteboard_get", str(sid)), "whiteboard_get")
        assert got.get("name") == "audit board"

        moved = _assert_ok(
            dispatch(window, "whiteboard_move_player", str(sid), "0", "60.0", "30.0", "home"),
            "whiteboard_move_player",
        )
        assert moved.get("ok") is True

        ann = _assert_ok(
            dispatch(
                window,
                "whiteboard_add_annotation",
                str(sid),
                json.dumps({"type": "arrow", "points": [{"x": 10, "y": 10}, {"x": 50, "y": 50}]}),
            ),
            "whiteboard_add_annotation",
        )
        assert ann.get("id"), ann

        svg = json.loads(dispatch(window, "whiteboard_generate_svg", str(sid), "800", "500"))
        assert "<svg" in svg.get("svg", ""), svg

        _assert_ok(
            dispatch(window, "whiteboard_set_formation", str(sid), "4-4-2", "home"),
            "whiteboard_set_formation",
        )
        _assert_ok(dispatch(window, "whiteboard_list"), "whiteboard_list")
        _assert_ok(dispatch(window, "whiteboard_list_templates"), "whiteboard_list_templates")
        _assert_ok(dispatch(window, "whiteboard_get_template", "4-3-3"), "whiteboard_get_template")
        _assert_ok(
            dispatch(window, "whiteboard_clear_annotations", str(sid)),
            "whiteboard_clear_annotations",
        )
        deleted = _assert_ok(dispatch(window, "whiteboard_delete", str(sid)), "whiteboard_delete")
        assert deleted.get("ok") is True

        # pure generators need no state
        _assert_ok(
            dispatch(window, "whiteboard_generate_pass", "10.0", "10.0", "50.0", "30.0", "#ff0000"),
            "whiteboard_generate_pass",
        )
        _assert_ok(
            dispatch(
                window,
                "whiteboard_generate_player_run",
                "10.0",
                "10.0",
                "40.0",
                "30.0",
                "#00ff00",
                "run1",
            ),
            "whiteboard_generate_player_run",
        )
        _assert_ok(dispatch(window, "check_whiteboard_status"), "check_whiteboard_status")
    finally:
        window.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# provider + settings + lifecycle: infra slots through the real bridge
# ---------------------------------------------------------------------------


def test_provider_settings_lifecycle_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        # cache round trip with int TTL as the Slot signature delivers
        set_out = _assert_ok(
            dispatch(window, "cache_set", "audit-key", json.dumps({"v": 42}), 120), "cache_set"
        )
        assert set_out.get("ok") is True
        got = json.loads(dispatch(window, "cache_get", "audit-key"))
        assert got == {"v": 42}, got
        _assert_ok(dispatch(window, "cache_stats"), "cache_stats")
        _assert_ok(dispatch(window, "cache_invalidate", "audit-key"), "cache_invalidate")
        _assert_ok(dispatch(window, "cache_invalidate_prefix", "audit"), "cache_invalidate_prefix")
        _assert_ok(dispatch(window, "cache_clear"), "cache_clear")

        calls = json.loads(dispatch(window, "get_recent_provider_calls", 5))
        assert isinstance(calls, list), calls
        _assert_ok(
            dispatch(window, "record_provider_call", "ollama", "ask", 12.5, True, 200),
            "record_provider_call",
        )
        _assert_ok(dispatch(window, "get_provider_status", "ollama"), "get_provider_status")
        _assert_ok(dispatch(window, "get_all_provider_statuses"), "get_all_provider_statuses")
        _assert_ok(dispatch(window, "get_provider_summary"), "get_provider_summary")

        overview = _assert_ok(dispatch(window, "get_settings_overview"), "get_settings_overview")
        assert "app" in overview and "gpu" in overview
        app_info = _assert_ok(dispatch(window, "get_app_info"), "get_app_info")
        assert app_info.get("version"), app_info
        _assert_ok(dispatch(window, "get_gpu_tier"), "get_gpu_tier")
        _assert_ok(dispatch(window, "get_current_yolo_variant"), "get_current_yolo_variant")
        _assert_ok(dispatch(window, "get_recommended_yolo_variant"), "get_recommended_yolo_variant")
        _assert_ok(dispatch(window, "get_model_cache_info"), "get_model_cache_info")

        gpu = _assert_ok(dispatch(window, "get_gpu_info"), "get_gpu_info")
        assert "tier" in gpu
        # metrics_text is a plain-text (Prometheus-style) slot by
        # contract, not JSON -- assert it returns a string without raising.
        metrics = dispatch(window, "metrics_text")
        assert isinstance(metrics, str), type(metrics)
        _assert_ok(dispatch(window, "profiler_status"), "profiler_status", allow_error=True)
        _assert_ok(dispatch(window, "profiler_reset"), "profiler_reset", allow_error=True)
    finally:
        window.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# storage + export + recruitment: payload slots through the real bridge
# ---------------------------------------------------------------------------


def test_storage_export_recruitment_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        mid = seed_match(window, "storage audit")
        # This audit issues dozens of analysis-category recruitment/export
        # slots back to back; the production limiter's shared "analysis"
        # bucket (5 tokens/min) would trip halfway through. Widen it for
        # this test only -- the limiter itself is unit-tested separately.
        window.bridge._rate_limiter.configure("analysis", 1000)

        fb = _assert_ok(
            dispatch(window, "submit_feedback", json.dumps({"rating": 5, "comment": "audit"})),
            "submit_feedback",
            allow_error=True,
        )
        assert ("feedback_id" in fb) or ("error" in fb), fb
        _assert_ok(dispatch(window, "get_feedback_stats"), "get_feedback_stats", allow_error=True)
        _assert_ok(
            dispatch(window, "submit_issue", json.dumps({"title": "t", "description": "d"})),
            "submit_issue",
            allow_error=True,
        )

        csv_out = _assert_ok(
            dispatch(window, "export_match_csv", str(mid)), "export_match_csv", allow_error=True
        )
        js_out = _assert_ok(
            dispatch(window, "export_match_json", str(mid)), "export_match_json", allow_error=True
        )
        assert any(k in js_out for k in ("path", "error")), js_out
        assert any(k in csv_out for k in ("path", "error")), csv_out
        _assert_ok(
            dispatch(window, "export_report_pdf", str(mid), "en"),
            "export_report_pdf",
            allow_error=True,
        )

        # recruitment: opponent profile round trip
        created = json.loads(
            dispatch(window, "opponent_create", "Audit Rivals", "Ligue 1", "France")
        )
        assert created.get("success") is True, created
        profile = created.get("profile") or {}
        pid = profile.get("id")
        assert pid, created
        got = _assert_ok(dispatch(window, "opponent_get", str(pid)), "opponent_get")
        assert got.get("profile", {}).get("team_name") == "Audit Rivals", got
        _assert_ok(dispatch(window, "opponent_list"), "opponent_list")
        _assert_ok(
            dispatch(window, "opponent_scouting_report", str(pid)), "opponent_scouting_report"
        )

        sl = _assert_ok(
            dispatch(
                window,
                "add_shortlist_entry",
                json.dumps(
                    {
                        "player_id": "audit-1",
                        "player_name": "Audited",
                        "position": "ST",
                        "club": "Clubs",
                    }
                ),
            ),
            "add_shortlist_entry",
        )
        assert sl.get("success") is True, sl
        _assert_ok(dispatch(window, "get_shortlist"), "get_shortlist")

        sc = json.loads(
            dispatch(
                window,
                "scout_network_add",
                "Audit Scout",
                "CM",
                "Club",
                "League",
                "7.5",
                json.dumps(["passing"]),
                json.dumps([]),
                "notes",
                "auditor",
                json.dumps([]),
            )
        )
        assert sc.get("success") is True, sc
        spid = (sc.get("player") or {}).get("id")
        if spid:
            _assert_ok(dispatch(window, "scout_network_get", str(spid)), "scout_network_get")
        _assert_ok(dispatch(window, "scout_network_stats"), "scout_network_stats")
        _assert_ok(
            dispatch(window, "scout_network_search", "", "", "0", "40", "", "0"),
            "scout_network_search",
        )
        _assert_ok(dispatch(window, "get_contract_alerts"), "get_contract_alerts")
        _assert_ok(dispatch(window, "get_contracts"), "get_contracts")
    finally:
        window.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# domain: analyzer slots either answer or return honest engine errors
# ---------------------------------------------------------------------------


def test_domain_slots_contract_through_real_bridge(qapp, tmp_path, monkeypatch):
    _reset_paths(monkeypatch, tmp_path)
    from kawkab.app import MainWindow

    window = MainWindow()
    try:
        # goalkeeper analytics slots must work (v0.13.2 fix: the lazy
        # property used to crash with AttributeError on every call)
        aerial = _assert_ok(
            dispatch(
                window,
                "compute_goalkeeper_aerial_command",
                json.dumps([{"minute": 10, "outcome": "caught", "cross_type": "cross"}]),
            ),
            "compute_goalkeeper_aerial_command",
        )
        assert "crosses_faced" in aerial, aerial
        dist = _assert_ok(
            dispatch(
                window,
                "compute_goalkeeper_distribution",
                json.dumps([{"minute": 15, "distribution_type": "throw", "outcome": "complete"}]),
            ),
            "compute_goalkeeper_distribution",
        )
        assert "short_attempts" in dist, dist
        saveq = _assert_ok(
            dispatch(
                window,
                "compute_goalkeeper_save_quality",
                json.dumps([{"minute": 20, "xg": 0.3, "saved": 1, "on_target": 1}]),
            ),
            "compute_goalkeeper_save_quality",
        )
        assert "save_rate" in saveq, saveq

        # laws are static content
        _assert_ok(dispatch(window, "get_all_laws"), "get_all_laws")
        _assert_ok(dispatch(window, "get_law_summary", "12"), "get_law_summary", allow_error=True)

        # engine-backed slots: honest error payloads when the engine is off
        for slot, args in [
            (
                "analyze_setpieces",
                (
                    json.dumps(
                        [
                            {
                                "set_piece_type": "corner",
                                "minute": 12,
                                "second": 30,
                                "team": "Reds",
                                "delivery_x": 90.0,
                                "delivery_y": 2.0,
                                "delivery_style": "inswinging",
                                "delivery_height": "medium",
                                "first_contact_x": 94.0,
                                "first_contact_y": 8.0,
                                "outcome": "shot",
                            }
                        ]
                    ),
                    "Reds",
                ),
            ),
            ("check_offside", ("90.0", "80.0", "50.0", "1")),
            ("classify_event_rule", ("goal", "99.0", "34.0", "home")),
            ("analyze_goalkeeper", ("Reds", json.dumps([]), json.dumps([]), "0")),
            (
                "analyze_possession",
                (
                    "Reds",
                    "Blues",
                    json.dumps(
                        [
                            {
                                "event_type": "pass",
                                "team": "Reds",
                                "timestamp": 1.0,
                                "x": 50.0,
                                "y": 34.0,
                            }
                        ]
                    ),
                ),
            ),
            (
                "analyze_substitutions",
                (
                    "Reds",
                    json.dumps([{"minute": 60, "player_off": "A", "player_on": "B"}]),
                    json.dumps([]),
                ),
            ),
            (
                "analyze_match_psychology",
                (
                    "Reds",
                    "Blues",
                    "Away",
                    json.dumps([{"event_type": "goal", "team": "Reds", "timestamp": 10.0}]),
                ),
            ),
            ("fetch_external_cards", ("123",)),
        ]:
            d = _assert_ok(dispatch(window, slot, *args), slot, allow_error=True)
            if "error" in d:
                assert isinstance(d["error"], str) and d["error"], slot
    finally:
        window.close()
        qapp.processEvents()
