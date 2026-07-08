# Deployment Checklist

A manual checklist covering the steps that **cannot be automated through code** — user/key creation, infrastructure prep, and troubleshooting.

---

## Prerequisites

### GitHub Secrets

Configure these in the repository under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|--------|---------|
| `FLASK_SECRET_KEY` | Flask session signing — use a long random string (≥32 chars) |
| `QNAP_HOST` | QNAP IP address or hostname |
| `QNAP_SSH_PORT` | SSH port (usually `22`) |
| `QNAP_USER` | SSH username on the QNAP |
| `QNAP_SSH_KEY` | Private SSH key for deploy access |
| `QNAP_GHCR_TOKEN` | GitHub PAT with `read:packages` scope |
| `ADMIN_BOOTSTRAP_PASSWORD` | Non-default admin password seeded during deploy (required) |
| `ADMIN_BOOTSTRAP_EMAIL` | Admin email to seed during deploy (optional, defaults to `admin@example.com`) |

### SSH Key Setup

1. Generate a dedicated deploy key (if one doesn't exist):
   ```bash
   ssh-keygen -t ed25519 -C "deploy@quizzler" -f deploy_key
   ```
2. Add the **public** key to the QNAP user's `~/.ssh/authorized_keys`.
3. Paste the **private** key contents into the `QNAP_SSH_KEY` GitHub secret.
4. Verify connectivity:
   ```bash
   ssh -i deploy_key -p <port> <user>@<qnap-host> "echo ok"
   ```

### GitHub Container Registry Token

1. Create a GitHub Personal Access Token with the `read:packages` scope.
2. Store it in the `QNAP_GHCR_TOKEN` secret — the deploy workflow uses it to pull images on the QNAP.

---

## QNAP Server Setup

### Create directories

```bash
mkdir -p /share/Container/quizzler/database
mkdir -p /share/Container/quizzler/data
mkdir -p /share/Container/quizzler/media/countries
```

### Host migration after rename (travel-quizzer -> quizzler)

If the host still uses legacy paths/container names, migrate data before running the renamed workflows:

```bash
# Stop old container if it is still present
docker stop travel-quizzer || true

# Move app data root (preserves database/media/backups)
if [ -d /share/Container/travel-quizzer ] && [ ! -d /share/Container/quizzler ]; then
  mv /share/Container/travel-quizzer /share/Container/quizzler
fi

# Optional: if legacy container object exists, rename it once
docker rename travel-quizzer quizzler || true
```

Migration impact summary:
- Deployment and backup workflows now read/write under `/share/Container/quizzler`.
- Runtime container name is now `quizzler` (including rollback generation names).
- Compose defaults now use `POSTGRES_DB=quizzler`.

### Verify Docker is available

Container Station installs Docker. Confirm:

```bash
docker --version
```

### Upload data files

`data/countries.json` is gitignored and not baked into the image. Copy it manually:

```bash
scp data/countries.json <user>@<qnap>:/share/Container/quizzler/data/countries.json
```

### Place quiz images

Each destination needs images organized by country ID and hint level:

```
media/countries/<id>/<level>a.jpg
media/countries/<id>/<level>b.jpg
```

Levels run 1 (easiest) through 5 (hardest). Current country IDs:

| ID | Country |
|----|---------|
| 1 | Bhutan |
| 2 | Bulgaria |
| 3 | Indonesia |
| 4 | Argentina |
| 5 | Israel |
| 6 | Myanmar |
| 7 | Australia |
| 8 | Azerbaijan |

### Internet Routing (QNAP + Home/Office Router)

To make Quizzler reachable from the public internet, route incoming traffic from your router to the QNAP host.

1. Reserve a static LAN IP for the QNAP in your router DHCP settings (for example `192.168.1.50`).
2. Set up Dynamic DNS (DDNS) on QNAP (for example MyQNAPcloud) or your own domain DNS so you have a stable hostname.
3. Prefer publishing through HTTPS on port `443` with QNAP Reverse Proxy:
  - QTS: **Control Panel -> Applications -> Reverse Proxy**
  - Add a rule from `https://<your-domain>:443` to `http://127.0.0.1:9696`
4. Configure router port forwarding:
  - External `443` -> QNAP LAN IP `443` (recommended)
  - Optional temporary fallback: external `9696` -> QNAP LAN IP `9696` (not recommended long-term)
5. Install/enable a trusted TLS certificate for your domain (Let's Encrypt in QNAP works well).
6. Validate from a network outside your LAN (mobile data):
  - `https://<your-domain>/` (or `http://<public-ip>:9696` only for temporary testing)

#### TLS Certificate Setup in QNAP (QTS)

Use these steps for a public certificate from Let's Encrypt.

1. Confirm DNS before requesting the certificate:
  - `A` record for `<your-domain>` points to your public WAN IP.
  - Router forwards external `443` to QNAP `443`.
  - Your ISP allows inbound `443` (some consumer ISPs block this).
2. In QTS, open **Control Panel -> Security -> Certificate & Private Key**.
3. Choose **Replace certificate -> Get from Let's Encrypt**.
4. Enter:
  - Domain name: `<your-domain>`
  - Email: certificate notification mailbox
  - Subject Alternative Name (optional): add `www.<your-domain>` if you use it
5. Submit and wait for issuance. QNAP stores this as the active system certificate.
6. Bind this certificate to HTTPS services and reverse proxy:
  - In the same certificate page, ensure the Let's Encrypt cert is set as default.
  - In **Control Panel -> Applications -> Reverse Proxy**, edit your rule and verify HTTPS listener/certificate selection uses the active cert.
7. Verify externally:
  - Open `https://<your-domain>` from mobile data.
  - Check browser certificate details: issuer is Let's Encrypt and hostname matches.

#### TLS Verification Commands

Run these from any machine outside your LAN.

```bash
# Show certificate subject/issuer/dates
echo | openssl s_client -servername <your-domain> -connect <your-domain>:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# Verify HTTPS response headers and TLS negotiation
curl -Ivs https://<your-domain>/ 2>&1 | sed -n '1,20p'

# Verify DNS resolves to expected public IP
dig +short <your-domain>
```

What to confirm:
- `subject` or SAN includes `<your-domain>`.
- `issuer` is your expected CA (for example, Let's Encrypt).
- `notAfter` is in the future and has sufficient remaining validity.
- `curl` shows a successful TLS handshake and HTTP status from your app.

#### Certificate Renewal / Expiry Handling

Let's Encrypt certificates are short-lived and should renew automatically in QTS.

1. Check current expiry date in QTS:
  - **Control Panel -> Security -> Certificate & Private Key**
2. Confirm auto-renew is enabled for the active Let's Encrypt certificate.
3. If the certificate is near expiry or expired:
  - Try **Renew** for the certificate (if shown in your QTS version).
  - If no renew action is available, run **Replace certificate -> Get from Let's Encrypt** again for the same domain.
4. After renewal, verify reverse proxy is still bound to the renewed certificate:
  - **Control Panel -> Applications -> Reverse Proxy**
5. Re-run the verification commands above and confirm the new `notAfter` value.

Operational recommendation:
- Add a recurring monthly check to verify `notAfter` and HTTPS reachability.
- Renew at least 14 days before expiry if auto-renew has not already completed.

Optional automation script (monthly check):

```bash
#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-example.com}"
WARN_DAYS="${WARN_DAYS:-14}"

end_date="$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null \
  | openssl x509 -noout -enddate | cut -d= -f2)"

if [[ -z "$end_date" ]]; then
  echo "ERROR: could not read certificate end date for $DOMAIN"
  exit 2
fi

end_epoch="$(date -d "$end_date" +%s)"
now_epoch="$(date +%s)"
days_left="$(( (end_epoch - now_epoch) / 86400 ))"

echo "domain=$DOMAIN"
echo "expires=$end_date"
echo "days_left=$days_left"

if [[ "$days_left" -le "$WARN_DAYS" ]]; then
  echo "ALERT: certificate expires in $days_left day(s), threshold is $WARN_DAYS"
  exit 1
fi

echo "OK: certificate validity is above threshold"
```

Example usage:

```bash
chmod +x check-cert.sh
./check-cert.sh your-domain.example
```

Cron example (runs monthly at 07:15 on day 1):

```bash
15 7 1 * * /path/to/check-cert.sh your-domain.example >> /var/log/check-cert.log 2>&1
```

#### Running on QNAP with Email Alerts

Recommended pattern: keep `check-cert.sh` as the checker and run it from a small wrapper that sends email when exit code is non-zero.

```bash
#!/usr/bin/env bash
set -euo pipefail

DOMAIN="your-domain.example"
LOG_FILE="/share/Public/check-cert.log"
TO_EMAIL="you@example.com"

if ! WARN_DAYS=14 /share/Public/check-cert.sh "$DOMAIN" >> "$LOG_FILE" 2>&1; then
  summary="$(tail -n 20 "$LOG_FILE")"
  {
    echo "Subject: TLS alert for $DOMAIN"
    echo "To: $TO_EMAIL"
    echo
    echo "The TLS certificate check reported an alert."
    echo
    echo "$summary"
  } | sendmail -t
fi
```

Schedule this wrapper in QTS:
1. **Control Panel -> System -> Task Scheduler**
2. Create a recurring task (monthly is typical).
3. Command points to the wrapper script.
4. Keep task output logging enabled so you can inspect history in QTS and in your log file.

Notes:
- `sendmail` must be available/configured on the QNAP. If it is not, use QNAP Notification Center or replace the mail block with a webhook (Slack/Discord/Teams/ntfy).
- Keep scripts on persistent storage (for example `/share/Public/`) so updates/reboots do not remove them.

Test your alert path safely:
- Force an alert by running with a high threshold:

```bash
WARN_DAYS=365 /share/Public/check-cert.sh your-domain.example; echo $?
```

- Or run the wrapper once manually and confirm you receive an email and see a new log entry.

If Let's Encrypt issuance fails:
- Re-check DNS propagation with `dig <your-domain> +short` and compare with your WAN IP.
- Ensure no conflicting forward/NAT rule is hijacking port `443`.
- Temporarily disable ISP/router security features that intercept HTTPS, then retry.
- If inbound `443` is impossible (CGNAT), use a tunnel solution (Cloudflare Tunnel/Tailscale Funnel) and terminate TLS there.

Manual certificate alternative:
- If you use another CA, import full chain certificate + private key in **Certificate & Private Key**.
- Re-bind/imported cert to reverse proxy and test with an external client.

Security notes:
- Avoid exposing QTS admin UI directly to the internet when possible.
- Keep QNAP firmware and Container Station updated.
- Keep SSH closed on WAN unless required; if required, use key auth and non-default port.
- If your ISP uses CGNAT and inbound forwarding fails, use VPN/Tailscale/Cloudflare Tunnel instead of direct port exposure.

---

## Post-Deploy Verification

- [x] Check container logs (automated in deploy workflow "Verify deployment"):
  ```bash
  docker logs quizzler
  ```
- [x] Confirm the app responds at `http://<qnap-ip>:9696` (automated health probe in deploy workflow).
- [x] Log in with the seeded admin account (`ADMIN_BOOTSTRAP_EMAIL` and `ADMIN_BOOTSTRAP_PASSWORD`) when bootstrap credentials are provided (automated in deploy workflow). If the deployment preserves an existing admin because no bootstrap secret was supplied, this remains a manual verification.
- [x] Default admin password is not used in deploy workflow (custom bootstrap password is required).

---

## Troubleshooting

### Deploy workflow fails to SSH

- Confirm the QNAP's SSH daemon is running and listening on the expected port.
- Ensure `QNAP_SSH_KEY` contains the full private key including `-----BEGIN/END-----` lines.
- Check `authorized_keys` permissions on the QNAP (`chmod 600`).

### Container won't start

- Check logs: `docker logs quizzler`
- Verify the bind-mounted directories exist and have correct ownership.
- Ensure port `9696` is not already in use on the host.

### Image pull fails on QNAP

- Verify `QNAP_GHCR_TOKEN` has `read:packages` scope and hasn't expired.
- Test manually:
  ```bash
  echo $TOKEN | docker login ghcr.io -u <github-user> --password-stdin
  docker pull ghcr.io/<org>/quizzler:latest
  ```

### Database issues

- The SQLite file lives at `/share/Container/quizzler/database/quiz_data.db`.
- If the container starts fresh with an empty database, run the seed script inside the container or copy a pre-seeded DB.
- File permission problems: ensure the container user can write to the `database/` directory.
