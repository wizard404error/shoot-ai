# Cloud Server API

## Auth

- `POST /auth/register` — Register with email/password
- `POST /auth/login` — Login with email/password
- `GET /auth/me` — Current user info (auth required)
- `POST /auth/change-password` — Change password (auth required)

## OAuth

- `GET /auth/oauth/providers` — List configured providers
- `GET /auth/oauth/{provider}/authorize` — Get OAuth authorize URL
- `POST /auth/oauth/{provider}/callback` — Exchange code for JWT
- `POST /auth/link-oauth` — Link OAuth account (auth required)
- `GET /auth/oauth/accounts` — List linked OAuth accounts (auth required)
- `POST /auth/oauth/unlink` — Unlink OAuth account (auth required)

## Sync

- `POST /sync/push` — Push operations to cloud
- `POST /sync/pull` — Pull operations from cloud

## Teams

- `POST /teams` — Create team
- `GET /teams` — List teams
- `POST /teams/{id}/invite` — Invite member
- `POST /teams/join/{token}` — Accept invite

## Health

- `GET /health` — Health status with uptime + DB check
- `GET /health/ready` — Readiness check
- `GET /health/live` — Liveness check
- `GET /metrics` — Prometheus-style metrics
