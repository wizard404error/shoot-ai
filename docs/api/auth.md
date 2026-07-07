# Auth & OAuth

## JWT Authentication

All cloud server endpoints use JWT bearer tokens (HS256, 30-day expiry).

```python
headers = {"Authorization": "Bearer <token>"}
```

## OAuth Providers

Configure via environment variables:

| Provider | Env Variables |
|----------|--------------|
| Google | `KAWKAB_GOOGLE_CLIENT_ID`, `KAWKAB_GOOGLE_CLIENT_SECRET` |
| GitHub | `KAWKAB_GITHUB_CLIENT_ID`, `KAWKAB_GITHUB_CLIENT_SECRET` |
| Apple | `KAWKAB_APPLE_CLIENT_ID`, `KAWKAB_APPLE_CLIENT_SECRET` |

## Desktop App Flow

The desktop app opens the provider's authorization page in the system browser,
then prompts the user to paste the redirect URL back into the app.

## RBAC Permissions

| Role | Permissions |
|------|-------------|
| ADMIN | Full access, team management |
| COACH | Match analysis, reports, tactics |
| ANALYST | Data analysis, model comparison |
| SCOUT | Recruitment search, shortlists |
| VIEWER | Read-only access |
