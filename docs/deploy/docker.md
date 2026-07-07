# Docker Deployment

## Quick Start

```bash
docker compose up -d
```

This starts:
- **postgres**: PostgreSQL 16 database
- **server**: Kawkab AI cloud server (FastAPI)
- **nginx**: Reverse proxy (port 80)

## Configuration

Create a `.env` file:

```env
KAWKAB_JWT_SECRET=your-strong-secret-here
KAWKAB_DB_PASSWORD=your-db-password
KAWKAB_GOOGLE_CLIENT_ID=
KAWKAB_GOOGLE_CLIENT_SECRET=
```

## Build Targets

```bash
# Cloud server only
docker build --target server -t kawkab-server .

# API only
docker build --target api -t kawkab-api .

# Full desktop app
docker build --target full -t kawkab-full .
```
