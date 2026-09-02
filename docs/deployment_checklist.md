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
  mkdir -p /share/CACHEDEV2_DATA/Container/quizzler/database
  mkdir -p /share/CACHEDEV2_DATA/Container/quizzler/data
  mkdir -p /share/CACHEDEV2_DATA/Container/quizzler/media/countries
  ```
- [ ] Ensure database path exists and is writable by container user `10001:10001`:
  ```bash
  touch /share/CACHEDEV2_DATA/Container/quizzler/database/quiz_data.db
  chown 10001:10001 /share/CACHEDEV2_DATA/Container/quizzler/database /share/CACHEDEV2_DATA/Container/quizzler/database/quiz_data.db || true
  chmod 770 /share/CACHEDEV2_DATA/Container/quizzler/database || true
  chmod 660 /share/CACHEDEV2_DATA/Container/quizzler/database/quiz_data.db || true
  ```

---

## 2) Content You Must Place on QNAP

- [ ] Upload the seed data file to QNAP. The checked-in development fixture is
  `data/destinations.json`; production deployments normally use the
  gitignored `data/countries.json` file or set `SEED_DATA_PATH` explicitly:
  ```bash
  scp data/countries.json <user>@<qnap>:/share/CACHEDEV2_DATA/Container/quizzler/data/countries.json
  ```
  If using the checked-in fixture instead, replace both file names in the
  command with `destinations.json`. The seed script prefers
  `data/countries.json` and falls back to `data/destinations.json`.
- [ ] Upload media files using this structure:
  ```text
  /share/CACHEDEV2_DATA/Container/quizzler/media/countries/<id>/<level>a.jpg
  /share/CACHEDEV2_DATA/Container/quizzler/media/countries/<id>/<level>b.jpg
  ```
- [ ] Confirm file permissions allow read access for the container process.

---

## 3) Network and TLS Setup (QNAP + Router)

- [ ] Reserve a static LAN IP for QNAP in router DHCP.
- [ ] Configure DDNS or DNS record for your domain.
- [ ] Obtain a TLS certificate before creating the HTTPS proxy rule:
  1. Ensure `<your-domain>` resolves to your public IP address and that the QNAP is reachable from the internet.
  2. In QTS, open **Control Panel -> System -> Security -> SSL Certificate & Private Key**.
  3. Choose **Replace Certificate** (or **Get Certificate**, depending on the QTS wording), select **Let's Encrypt**, and enter `<your-domain>` and a valid email address.
  4. Allow the certificate request to complete. Let’s Encrypt validation commonly requires temporary router forwarding of external port `80` to QNAP port `80`; remove that forwarding afterward if it is not otherwise needed.
  5. Confirm the new certificate is listed and covers `<your-domain>`. Do not use **Custom Root Certificate** for this; that option installs a CA certificate for trust validation and is not the public server certificate used by Quizzler.
- [ ] Configure a QNAP reverse proxy rule in QTS:
  1. Open **Control Panel -> Network & File Services -> Network Access -> Reverse Proxy**.
  2. Select **Create** or **Add**.
  3. Enter a descriptive name, such as `quizzler`.
  4. Set the source/listening side to:
     - Protocol: `HTTPS`
     - Hostname: `<your-domain>`
     - Port: `443`
  5. Set the destination/forwarding side to:
     - Protocol: `HTTP`
     - Hostname: `127.0.0.1`
     - Port: `9696`
  6. Save and enable the rule. Do not enable WebSocket or path rewriting unless your QTS version requires it; Quizzler is served from `/`.
  7. QTS uses the active system SSL certificate for the HTTPS listener; there is no certificate selector in the reverse-proxy rule on this QTS version.
  8. If QTS asks which service owns port `443`, keep the reverse proxy bound to `443` and avoid assigning the same hostname/port to another QTS service.
- [ ] Configure router forwarding:
  - External `443` -> QNAP `443`
  - Do not forward external `9696`; it is only the local proxy destination.
- [ ] Confirm the domain certificate remains the active system certificate and renew it before expiry. Let’s Encrypt certificates normally expire after 90 days; QTS may renew them automatically when validation remains possible.
- [ ] Verify externally (outside LAN):
  ```bash
  echo | openssl s_client -servername <your-domain> -connect <your-domain>:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
  curl -Ivs https://<your-domain>/ 2>&1 | sed -n '1,20p'
  dig +short <your-domain>
  ```

---

## 4) First Application Deployment

The reverse proxy can be configured before the application is deployed, but it will return `503 Service Unavailable` until a container is listening on QNAP port `9696`.

- [ ] Complete the GitHub Actions setup in [deployment_automation_prerequisites.md](deployment_automation_prerequisites.md), including the required repository secrets and QNAP SSH access.
- [ ] Confirm the QNAP host has the persistent directories from section 1 and that the seed data and media are in place.
- [ ] Create and push a version tag from the repository after the changes to deploy:
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
  The deploy workflow runs for tags beginning with `v`; pushing to `main` alone does not deploy the application.
- [ ] Wait for the `Deploy to QNAP Container Station` GitHub Actions workflow to finish successfully.
- [ ] Confirm the container is running and the public health endpoint returns `{"status":"healthy"}` using the checks in section 5.

---

## 5) Release-Day Checklist (Tag Deploy)

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
- [ ] Confirm the reverse proxy reaches Quizzler, rather than checking only the Apache `Server` header:
  ```bash
  curl -fsS https://<your-domain>/health
  ```
  The expected response is `{"status":"healthy"}`. This endpoint is served by Quizzler and checks that its database connection is working. The `Server: Apache` header may still be present because QTS handles the HTTPS connection in front of the container.
- [ ] Validate TLS certificate presented to public clients:
  ```bash
  echo | openssl s_client -servername <your-domain> -connect <your-domain>:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
  ```
- [ ] Validate admin login manually in browser using bootstrap admin credentials.

---

## 6) Troubleshooting on QNAP

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
  - `/share/CACHEDEV2_DATA/Container/quizzler/database`
  - `/share/CACHEDEV2_DATA/Container/quizzler/data`
  - `/share/CACHEDEV2_DATA/Container/quizzler/media`
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
  ls -l /share/CACHEDEV2_DATA/Container/quizzler/database/quiz_data.db
  ```
- [ ] If DB is empty on first setup, seed data in the running container:
  ```bash
  docker exec quizzler /app/.venv/bin/python -m scripts.seed_db
  ```

---

## 7) Optional Recurring Ops Task (QNAP)

- [ ] Add monthly certificate expiry/reachability check in QTS Task Scheduler.
- [ ] Keep QNAP firmware and Container Station updated.
- [ ] Avoid exposing QTS admin UI directly to the public internet.
