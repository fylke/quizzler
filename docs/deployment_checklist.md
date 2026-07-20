# Deployment Checklist (Manual QNAP Tasks)

This checklist is intentionally focused on actions you perform manually on the QNAP host and network.

For GitHub-side deployment setup and workflow prerequisites, see [deployment_automation_prerequisites.md](deployment_automation_prerequisites.md).

---

## 1) One-time QNAP Host Preparation

- [ ] Confirm Docker CLI is available on QNAP:
  ```bash
  docker --version
  ```
- [ ] Create persistent app directories:
  ```bash
  mkdir -p /share/Container/quizzler/database
  mkdir -p /share/Container/quizzler/data
  mkdir -p /share/Container/quizzler/media/countries
  ```
- [ ] Ensure database path exists and is writable by container user `10001:10001`:
  ```bash
  touch /share/Container/quizzler/database/quiz_data.db
  chown 10001:10001 /share/Container/quizzler/database /share/Container/quizzler/database/quiz_data.db || true
  chmod 770 /share/Container/quizzler/database || true
  chmod 660 /share/Container/quizzler/database/quiz_data.db || true
  ```

### If migrating from legacy name `travel-quizzer`

- [ ] Stop old container and move host data path:
  ```bash
  docker stop travel-quizzer || true
  if [ -d /share/Container/travel-quizzer ] && [ ! -d /share/Container/quizzler ]; then
    mv /share/Container/travel-quizzer /share/Container/quizzler
  fi
  docker rename travel-quizzer quizzler || true
  ```

---

## 2) Content You Must Place on QNAP

- [ ] Upload seed data file to QNAP:
  ```bash
  scp data/countries.json <user>@<qnap>:/share/Container/quizzler/data/countries.json
  ```
- [ ] If using legacy seed file, upload fallback path instead:
  ```bash
  scp data/destinations.json <user>@<qnap>:/share/Container/quizzler/data/destinations.json
  ```
- [ ] Upload media files using this structure:
  ```text
  /share/Container/quizzler/media/countries/<id>/<level>a.jpg
  /share/Container/quizzler/media/countries/<id>/<level>b.jpg
  ```
- [ ] Confirm file permissions allow read access for the container process.

---

## 3) Network and TLS Setup (QNAP + Router)

- [ ] Reserve a static LAN IP for QNAP in router DHCP.
- [ ] Configure DDNS or DNS record for your domain.
- [ ] Configure QNAP reverse proxy rule:
  - Source: `https://<your-domain>:443`
  - Destination: `http://127.0.0.1:9696`
- [ ] Configure router forwarding:
  - External `443` -> QNAP `443`
  - Optional temporary test: external `9696` -> QNAP `9696`
- [ ] Install/renew TLS cert in QTS under Security -> Certificate & Private Key.
- [ ] Verify externally (outside LAN):
  ```bash
  echo | openssl s_client -servername <your-domain> -connect <your-domain>:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
  curl -Ivs https://<your-domain>/ 2>&1 | sed -n '1,20p'
  dig +short <your-domain>
  ```

---

## 4) Release-Day Checklist (Tag Deploy)

Run these on release day after pushing a release tag, for example `v1.4.0`.

- [ ] Confirm container is running:
  ```bash
  docker ps --format '{{.Names}}\t{{.Status}}' | grep '^quizzler\b'
  ```
- [ ] Confirm expected image is in use:
  ```bash
  docker inspect quizzler --format '{{.Image}}'
  ```
- [ ] Review recent logs for startup issues:
  ```bash
  docker logs --tail 120 quizzler
  ```
- [ ] Validate local health endpoint from host context:
  ```bash
  docker exec quizzler python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/health', timeout=5).read().decode('utf-8'))"
  ```
- [ ] Validate host port mapping from QNAP shell:
  ```bash
  curl -fsS http://127.0.0.1:9696/health
  ```
- [ ] Validate public endpoint from outside LAN:
  ```bash
  curl -Ivs https://<your-domain>/ 2>&1 | sed -n '1,20p'
  ```
- [ ] Validate TLS certificate presented to public clients:
  ```bash
  echo | openssl s_client -servername <your-domain> -connect <your-domain>:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
  ```
- [ ] Validate admin login manually in browser using bootstrap admin credentials.

---

## 5) Troubleshooting on QNAP

### SSH access failures

- [ ] Ensure SSH service is enabled and listening on expected port.
- [ ] Verify `~/.ssh/authorized_keys` ownership and permissions.
- [ ] Confirm the deployed public key matches the private key used by your deployment automation.

### Container not starting

- [ ] Inspect logs:
  ```bash
  docker logs quizzler
  ```
- [ ] Confirm required bind-mount paths exist:
  - `/share/Container/quizzler/database`
  - `/share/Container/quizzler/data`
  - `/share/Container/quizzler/media`
- [ ] Ensure port `9696` is free on host:
  ```bash
  ss -ltnp | grep ':9696'
  ```

### Image pull/auth issues (host-side validation)

- [ ] Test GHCR login from QNAP shell:
  ```bash
  echo "$TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
  ```
- [ ] Pull exact image reference used by deployment (digest preferred):
  ```bash
  docker pull ghcr.io/<org>/quizzler@sha256:<digest>
  ```

### Database issues

- [ ] Confirm SQLite file exists:
  ```bash
  ls -l /share/Container/quizzler/database/quiz_data.db
  ```
- [ ] If DB is empty on first setup, seed data in the running container:
  ```bash
  docker exec quizzler /app/.venv/bin/python -m scripts.seed_db
  ```

---

## 6) Optional Recurring Ops Task (QNAP)

- [ ] Add monthly certificate expiry/reachability check in QTS Task Scheduler.
- [ ] Keep QNAP firmware and Container Station updated.
- [ ] Avoid exposing QTS admin UI directly to the public internet.
