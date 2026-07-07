# Webhooks

## Registration

```python
from kawkab.services.webhook_service import WebhookService

svc = WebhookService()
svc.register("https://example.com/hook", events=["match.updated", "drift.detected"])
```

## Event Delivery

Webhooks are delivered with HMAC-SHA256 signing. Retries on failure.

## Management

```python
svc.list_webhooks()
svc.unregister("hook-id")
```
