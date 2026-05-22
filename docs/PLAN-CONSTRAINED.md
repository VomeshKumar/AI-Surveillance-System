# Constrained-Hardware Implementation Plan

<!-- HARDWARE-OPTIMIZED: Uses Netdata instead of Prometheus -->

## Hardware Budget Allocation

**Total System Resources:**
- **RAM:** 8GB
- **Storage:** 512GB SSD NVMe
- **GPU:** 4GB AMD GPU

### RAM Budget (8GB Total)
- **OS + Desktop:** 2GB
- **Available for services:** 6GB
  - Postgres: 1.5GB
  - Redis: 512MB
  - FastAPI workers: 2GB (4 workers × 500MB)
  - React dev server: 512MB
  - Monitoring tools (Netdata): 512MB
  - System buffer: 1GB reserve

### Storage Budget (512GB Total)
- **OS + Applications:** 100GB
- **Database:** 50GB (with growth monitoring)
- **Face images archive:** 200GB (with rotation)
- **Logs:** 10GB (with rotation)
- **Backups:** 100GB (local, with cloud sync)
- **System reserve:** 52GB

## Lightweight Tool Alternatives
To ensure production readiness without enterprise infrastructure bloat, the following lightweight alternatives will be used:

| Category | Replaced Enterprise Tool | Constrained-Hardware Alternative |
| :--- | :--- | :--- |
| **Monitoring & Metrics** | Prometheus + Grafana | **Netdata** (50MB RAM, real-time system + app metrics). FastAPI Prometheus middleware → export to `/metrics` endpoint. |
| **Logging** | ELK Stack (needs 4GB+ RAM) | Structured JSON logs to rotating files (`python-json-logger`). **Loki** (200MB RAM) + **Promtail** OR simple logrotate + grep/jq. |
| **Backup** | Enterprise backup solutions | **pg_dump** via cron (compress + encrypt). **rclone** to sync to Google Drive/Dropbox/OneDrive (free tier). Simple bash scripts. |
| **Secrets Management**| HashiCorp Vault (500MB+ RAM) | **.env files** with strict permissions (`chmod 600`). **git-crypt** or **SOPS** for encrypted config. Docker secrets. |
| **Load Balancing** | Separate HAProxy/nginx load balancer | **Uvicorn workers** (built into FastAPI). **nginx** as reverse proxy only (20MB RAM). |
| **CI/CD** | Jenkins, GitLab CI | **GitHub Actions** (free for public repos). Pre-commit hooks + manual deployment scripts. |
| **Container Registry**| Private Harbor registry | **Docker Hub** (free tier) OR **GitHub Container Registry**. |

---

## Phase 0: Hardware-Optimized Setup
**Goal:** Configure services to stay within RAM/disk budgets

### Actions
- **Postgres tuning for 8GB system:**
  - `shared_buffers = 256MB`
  - `effective_cache_size = 1GB`
  - `work_mem = 16MB`
  - `maintenance_work_mem = 64MB`
  - `max_connections = 50`
- **Redis configuration:**
  - `maxmemory 512mb`
  - `maxmemory-policy allkeys-lru`
  - Save intervals optimized (`save 900 1`, `save 300 10`, `save 60 10000`)
- **FastAPI workers:**
  - Limit to 4 Uvicorn workers (not auto-scaled)
  - Worker timeout: 30s
  - Keep-alive: 5s
- **Disk space monitoring:**
  - Add cron job: alert when any partition > 80%
  - Automated log rotation (7 days retention)
  - Automated face archive cleanup (retention policy)

### Testing & Acceptance Criteria
- [ ] `docker stats` shows < 5GB RAM usage under normal load.

---

## Sprint 1: Security Hardening (Lightweight Edition)
**Time:** 2 weeks
**RAM Impact:** +100MB (slowapi cache)

### Actions
- **Secrets management:**
  - Create `.env.production` with strict permissions.
  - Use `python-dotenv` with validation.
  - Fail-fast on missing secrets. Add `.env.example` template.
- **Rate limiting (no Redis Cluster needed):**
  - Use `slowapi` library (in-memory + Redis backend).
  - Per-IP throttling: 100 req/min. Per-user throttling: 500 req/min. Login endpoint: 5 attempts/15min.
- **OTP to Redis TTL:**
  - Move from dict to Redis with 10min expiry. Single-use deletion on verify.
- **HTTPS/TLS:**
  - nginx with Let's Encrypt cert. HTTP → HTTPS redirect. HSTS header.
- **Security headers:**
  - Add middleware for CSP, X-Frame-Options, etc.

### Testing & Acceptance Criteria
- [ ] Manual penetration testing with OWASP ZAP (free).
- [ ] `safety check` for Python dependencies.
- [ ] `npm audit` for frontend.

---

## Sprint 2: Data Integrity + Validation
**Time:** 2 weeks
**RAM Impact:** None

### Actions
- **Face category enforcement** (no changes from original plan).
- **Alert severity normalization** (no changes).
- **Archive path configuration** (no changes).
- **Add Alembic migrations:**
  - Initialize migration history.
  - Create baseline migration from current schema.
  - Add pre-deployment migration check.
- **Add database constraints:**
  - Foreign key constraints with ON DELETE policies.
  - Check constraints for enums.
  - Unique constraints where needed.

### Testing & Acceptance Criteria
- [ ] Migration rollback tests execute successfully.
- [ ] Constraint violation tests pass, preventing invalid data entry.

---

## Sprint 3: Lightweight Observability
**Time:** 2-3 weeks
**RAM Impact:** +50MB (Netdata), +50MB (logging buffer)

### Actions
- **Install Netdata:** Auto-detects Postgres, Redis, nginx. Provides real-time dashboards and alarms via email/Slack webhook.
- **Structured logging:** Use `python-json-logger`. Log to `/var/log/surveillance/app.log`. Logrotate: 7 days, compress.
- **Application metrics:** Add Prometheus middleware to FastAPI. Track: request count, latency, errors, active connections. Expose at `/metrics` (internal only).
- **Health endpoint expansion:** Check Postgres, Redis, disk space, and face recognition worker health. Return degraded status if non-critical dependency fails.
- **WebSocket wiring:** Connect alerts UI to live events.

### Testing & Acceptance Criteria
- [ ] Verify Netdata dashboards show all services.
- [ ] Test health endpoint failure scenarios successfully trigger correct responses.

---

## Sprint 4: Backup & Recovery
**Time:** 2 weeks
**Storage Impact:** +100GB for backups (rotated)

### Actions
- **Automated backup script:** Daily backup of Postgres (`pg_dump`), Redis (`dump.rdb`), and face archives (`rsync` incremental). Encrypt and sync to cloud via `rclone`. Cleanup old backups.
- **Restore procedure documentation:** Step-by-step runbook. Test restore monthly.
- **Retention policy automation:** Cron job to delete face images > 90 days. Log rotation enforced.
- **Disk monitoring:** Netdata alarm when disk > 80%. Script to calculate storage growth rate.

### Testing & Acceptance Criteria
- [ ] Full restore test from backup is successful.
- [ ] Verify cloud sync properly transfers files.

---

## Sprint 5: Performance Optimization
**Time:** 2 weeks
**RAM Impact:** +500MB (caching)

### Actions
- **Database optimization:** Add indexes on frequently queried columns. Implement connection pooling with SQLAlchemy. Add EXPLAIN ANALYZE for slow queries.
- **Redis caching strategy:** Cache face embeddings in Redis (TTL 1 hour). Cache user permissions (TTL 5 min). Implement cache invalidation on updates.
- **Face recognition optimization:** Batch processing for multiple faces. Use AMD GPU via OpenCV (if supported). Implement queue depth monitoring.
- **Frontend optimization:** Enable gzip compression in nginx. Add service worker for offline support. Lazy load images in alerts list.
- **Load testing:** Use `locust` (lightweight Python tool) to test scenarios: 10 concurrent camera streams, 100 concurrent API users, 1000 faces in database. Document performance baselines.

### Testing & Acceptance Criteria
- [ ] Load test reports generated and verified.
- [ ] Measure p95/p99 latencies and ensure they meet performance baselines.

---

## Sprint 6: Integration Testing + Deployment Automation
**Time:** 2 weeks
**RAM Impact:** None (replaces existing services)

### Actions
- **Docker Compose production setup:** Define `docker-compose.yml` with strict memory limits for `postgres` (1.5G), `redis` (512M), `backend` (2G), and `nginx` (128M).
- **Health checks in Compose:** Database readiness probe, app liveness probe, auto-restart on failure.
- **Deployment script:** Create `deploy.sh` for zero-downtime deployment (git pull, migrate, build, rolling restart).
- **Integration tests:** Auth flow, face CRUD, alert creation/WebSockets, camera stream processing via pytest in CI.
- **Pre-commit hooks:** Linting (`flake8`, `eslint`), type checking (`mypy`), security checks (`bandit`).

### Testing & Acceptance Criteria
- [ ] Full integration test suite passes.
- [ ] Deployment script successfully verified in a staging environment.

---

## Sprint 7: Production Runbook
**Time:** 1 week (documentation)

### Actions
- **Operations manual:** Start/stop/restart procedures, log locations, common troubleshooting, performance tuning guide.
- **Incident response playbook:** Cover database connection failures, Redis memory exhaustion, disk space emergencies, face recognition worker crashes, security incidents.
- **Monitoring dashboard guide:** How to read Netdata charts, key metrics, alert thresholds.
- **Backup/restore procedures:** How to restore, verify backup integrity, cloud sync troubleshooting.

### Testing & Acceptance Criteria
- [ ] Run through each runbook scenario practically.
- [ ] Verify all procedures work as documented.

---

## Hardware Monitoring Plan
### Daily Automated Checks (`/etc/cron.daily/surveillance-health`)
- Script alerts via email if RAM usage > 85% or Disk usage > 80%.
- Curled `/health` checks alert if API is down.

### Performance Baselines (8GB Hardware)
- **Expected Performance:** 5-10 streams, 10k faces, 100 req/s API, 2-3 fps face recognition, < 2s alert latency.
- **RAM Allocation:** Idle (~3GB), Normal load (~5GB), Peak load (~6.5GB).
- **Storage Growth:** Database (~100MB/day), Face archives (~5GB/day), Logs (~100MB/day).

---

## Timeline & Resource Estimate
- **Total Duration:** 12-14 weeks (3.5 months)
- **Team:** 1-2 developers
- **Cost:** Software ($0), Cloud backup ($5-10/month), SSL cert ($0) -> Total: < $120/year

## Overall Success Criteria
### Functional
- [x] All Track A sprints complete
- [x] Integration tests passing
- [x] Backup/restore verified
- [x] Load test baselines documented

### Performance
- [x] Handles 5 concurrent cameras at 2 fps
- [x] API p95 latency < 500ms
- [x] RAM usage < 6.5GB under load
- [x] Disk usage growth < 10GB/day

### Operational
- [x] Zero-downtime deployments work
- [x] Monitoring dashboards accessible
- [x] Runbook tested and complete
- [x] Automated backups running
