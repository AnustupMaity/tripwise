# TripWise Production Hardening Checklist

## Gateway And API Protection

- Enable gateway-level IP and bot protection in front of `/api/v1/*`.
- Enforce per-route throttles at gateway for auth and report endpoints.
- Block high-risk geographies if business policy allows.
- Add WAF rules for SQL injection, XSS, and request smuggling patterns.

## Secrets Management

- Move all runtime secrets to a managed secret store.
- Rotate API keys, OAuth secrets, and webhook tokens every 90 days.
- Remove `.env` secrets from CI logs and deployment artifacts.
- Use separate secret scopes for dev, staging, and prod.

## Audit And Observability

- Ingest API audit logs with `x-request-id` into centralized logging.
- Create alerts for repeated `429` spikes on auth/report endpoints.
- Add dashboard for request latency, error rate, and dispute workflow failures.
- Track report generation success/failure and delivery queue latency.

## Data Protection And Backups

- Enable automated Postgres backups with point-in-time restore.
- Validate restore process monthly in a staging environment.
- Add data-retention policy for reports and notification events.
- Encrypt backup snapshots and restrict restore permissions.

## Test Coverage

- Add unit tests for invite edge cases:
  - duplicate invite rejection
  - last-admin removal protection
  - member-count synchronization
  - invite-all partial success behavior
- Add unit tests for split validation paths in expense service.
- Add integration tests for report generation (`pdf`, `excel`, `json`).
- Add auth tests for email-only OTP and forgot-password reset path.

## Release Readiness Gates

- Block deploy if tests fail or coverage drops below threshold.
- Block deploy if migration checks fail.
- Run synthetic smoke tests after deployment for auth, trip, expense, and report APIs.
