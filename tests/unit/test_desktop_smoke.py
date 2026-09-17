"""Desktop smoke: the Settings workspace must stay wired end-to-end.

The Settings contracts panel shipped fully built (bridge slot -> handler ->
JS renderer) but with NO mount point in index.html, so it silently never
rendered. These tests pin the whole chain so a rename or removal anywhere
along it fails loudly here instead of vanishing from the UI.

Note on the JS layout: the shipped UI loads dist/app.bundle.min.js (built
by scripts/bundle-js.mjs, which inlines js/app-settings.js), so the
wiring assertions check the bundle AND its sources, never a bare
<script src="js/app-settings.js"> tag.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src" / "kawkab"
WEB = SRC / "web"

sys_path_guard = str(PROJECT_ROOT / "src")
import sys  # noqa: E402  (after PROJECT_ROOT derivation)

if sys_path_guard not in sys.path:
    sys.path.insert(0, sys_path_guard)


class TestSettingsWorkspaceWiring:
    """index.html mounts <-> bundle content <-> bridge chain."""

    def test_settings_mount_points_exist_in_index_html(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        for mount in (
            "settings-overview",
            "settings-model-list",
            "settings-cache-size",
            "settings-contract-alerts",
        ):
            assert f'id="{mount}"' in html, (
                f"index.html lost the #{mount} mount point — the Settings "
                "panel would silently render nothing"
            )

    def test_shipped_bundle_contains_settings_workspace(self):
        """The shipped bundle inlines app-settings.js; it must keep doing so."""
        bundle = WEB / "dist" / "app.bundle.min.js"
        if not bundle.exists():
            return  # bundle is a build artifact; sources checked below
        js = bundle.read_text(encoding="utf-8")
        for needle in (
            "KawkabSettings",
            "settings-contract-alerts",
            "get_contract_alerts",
            "get_settings_overview",
        ):
            assert needle in js, f"shipped bundle lost Settings symbol {needle}"

    def test_app_settings_js_targets_existing_mounts(self):
        js = (WEB / "js" / "app-settings.js").read_text(encoding="utf-8")
        for mount in (
            "settings-overview",
            "settings-model-list",
            "settings-contract-alerts",
        ):
            assert f"getElementById('{mount}')" in js, f"app-settings.js no longer targets #{mount}"
        assert "get_settings_overview" in js
        assert "get_contract_alerts" in js

    def test_bundle_script_tag_present_in_index_html(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        assert re.search(r'src="[^"]*app\.bundle\.min\.js"', html), (
            "index.html no longer loads the app bundle"
        )

    def test_bridge_chain_for_settings_slots(self):
        """bridge.py slot -> bridge_analysis handler, both sides present."""
        bridge = (SRC / "ui" / "bridge.py").read_text(encoding="utf-8")
        handlers = (SRC / "ui" / "bridge_handlers" / "bridge_analysis.py").read_text(
            encoding="utf-8"
        )
        for slot in ("get_settings_overview", "get_contract_alerts", "get_contracts"):
            assert f"def {slot}" in bridge, f"bridge.py lost slot {slot}"
            assert f"def {slot}" in handlers, f"bridge_analysis lost handler {slot}"

    def test_handler_reads_storage_contract_methods(self):
        """get_contract_alerts must keep consuming get_contracts_expiring_soon
        and derive the critical/warning split the panel renders."""
        handlers = (SRC / "ui" / "bridge_handlers" / "bridge_analysis.py").read_text(
            encoding="utf-8"
        )
        assert "get_contracts_expiring_soon(180)" in handlers, (
            "get_contract_alerts no longer queries the 180-day expiring window"
        )
        assert "critical" in handlers and "warning" in handlers, (
            "get_contract_alerts no longer derives alert levels"
        )


class TestDesktopStorageStartupPath:
    """The GUI startup runs StorageService.initialize() before Qt starts;
    a regression there silently discards every save (historical bug)."""

    def test_app_startup_invokes_storage_initialize(self):
        app_src = (SRC / "app.py").read_text(encoding="utf-8")
        assert "asyncio.run(self.storage.initialize())" in app_src, (
            "app.py no longer initializes storage at startup — all persistence "
            "calls would silently no-op (self._conn stays None)"
        )

    def test_initialize_on_real_migrated_db_wires_wal_conn(self):
        """Smoke the real chain: migrations 001-030 -> initialize() -> WAL conn."""

        from kawkab.core.migration_manager import MigrationManager
        from kawkab.services.storage_service import StorageService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "smoke.db"
            migrations_dir = PROJECT_ROOT / "src" / "kawkab" / "migrations"
            MigrationManager(db_path, migrations_dir).migrate()

            svc = StorageService()
            svc._pg = None
            svc._use_postgres = False
            svc._db_path = db_path
            svc._conn = None
            import asyncio

            asyncio.run(svc.initialize())
            assert svc._conn is not None, "initialize() must open the connection"
            mode = svc._conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert str(mode).lower() == "wal"
            svc._conn.close()

    def test_pg_mode_initialize_delegates_to_adapter(self):
        """The initialize-in-PG-mode regression: must call _pg.initialize()."""
        import asyncio

        from kawkab.services.storage_service import StorageService

        svc = StorageService(dsn="postgresql://user:pass@localhost:5432/kawkab_test")
        assert svc._use_postgres is True and svc._pg is not None
        calls = []

        async def fake_init():
            calls.append(True)

        svc._pg.initialize = fake_init
        asyncio.run(svc.initialize())
        assert calls, "initialize() in PG mode must bring up the adapter pool"
