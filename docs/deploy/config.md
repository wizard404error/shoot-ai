# Configuration

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAWKAB_JWT_SECRET` | (required) | JWT signing secret |
| `KAWKAB_CLOUD_DB` | `~/.kawkab/cloud.db` | Cloud DB path |
| `KAWKAB_CLOUD_URL` | `http://localhost:8741` | Server URL |
| `KAWKAB_DB_PASSWORD` | `changeme` | PostgreSQL password |
| `KAWKAB_GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `KAWKAB_GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret |
| `KAWKAB_GITHUB_CLIENT_ID` | — | GitHub OAuth client ID |
| `KAWKAB_GITHUB_CLIENT_SECRET` | — | GitHub OAuth client secret |
| `KAWKAB_APPLE_CLIENT_ID` | — | Apple OAuth client ID |
| `KAWKAB_APPLE_CLIENT_SECRET` | — | Apple OAuth client secret |

## Database

- **Default**: SQLite at `~/.kawkab/kawkab.db`
- **Cloud**: SQLite at `~/.kawkab/cloud.db`
- **PostgreSQL**: Set `KAWKAB_DB_URL` for asyncpg pool
