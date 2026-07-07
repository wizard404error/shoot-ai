# Architecture

## Overview

Kawkab AI follows a layered architecture:

```
┌─────────────────────────────────────┐
│  Qt Desktop UI (QWebEngineView)     │
│  ┌───────────────┐  ┌───────────┐  │
│  │  HTML/CSS/JS  │  │ 3D Pitch  │  │
│  └───────┬───────┘  └───────────┘  │
│          │ QWebChannel              │
│  ┌───────┴───────┐                  │
│  │  Bridge (RPC) │                  │
│  └───────┬───────┘                  │
└──────────┼──────────────────────────┘
           │
┌──────────┼──────────────────────────┐
│  ┌───────┴───────┐                  │
│  │  Services     │ ◄── FastAPI REST │
│  │  Layer        │      (optional)  │
│  └───────┬───────┘                  │
│  ┌───────┴───────┐                  │
│  │  Core         │                  │
│  │  Analytics    │                  │
│  └───────┬───────┘                  │
│  ┌───────┴───────┐                  │
│  │  Storage      │                  │
│  │  (SQLite/     │                  │
│  │   PostgreSQL) │                  │
│  └───────────────┘                  │
└─────────────────────────────────────┘
```

## Key Layers

- **Web UI**: HTML/CSS/JS in Qt QWebEngineView, i18n (English/Arabic)
- **Bridge**: QWebChannel-based RPC layer, 100+ @Slot methods
- **Services**: 140+ service modules (CV, analytics, ML, data providers)
- **Core**: 50+ analytical algorithms (xG, VAEP, xT, pitch control, formations)
- **Storage**: SQLite (default), PostgreSQL (optional), asyncpg pool
- **Cloud**: FastAPI server with JWT auth, OAuth, sync, teams, webhooks
