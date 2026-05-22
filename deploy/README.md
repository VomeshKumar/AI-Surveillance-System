# Backend Ops Templates (Host-Applied)

These templates are for non-Docker deployments and align with the production backend plan.

## Included

- `pgbouncer.ini.template`
- `users.txt.template`
- `systemd/aisurv-api.service`
- `systemd/aisurv-consumer.service`
- `systemd/aisurv-ai.service`
- `nginx/aisurveillance.conf`

## Notes

- Keep frontend static hosting and API route paths unchanged.
- WebSocket endpoint remains `/ws`.
- `POSTGRES_URL` in backend should target PgBouncer in production.
- Apply and validate on staging before production rollout.

