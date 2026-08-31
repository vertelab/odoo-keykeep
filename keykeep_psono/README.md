# keykeep_psono — Personal Password Vault (psono-protocol)

Zero-knowledge personal password vault embedded in Odoo as HTTP controllers,
byte-compatible with the psono protocol (verified against psono-web v4.8.0 and
psono-server 7.3.6).

**Trust model:** client-side encryption. The server stores only ciphertext,
nonces and wrapped keys — Odoo administrators cannot read vault contents.
The user's master password never leaves the browser.

**Identity:** each vault user is tied 1:1 to a `res.users` record by email.
Registration is gated by the Odoo session (no open registration).

## Architecture

```
psono-web v4.8.0 (static, served from Odoo at /keykeep/psono/web/)
   │  SERVER_URL = <host>/keykeep/psono  (relative in config.json)
   ▼
Caddy (ledningssystem.vertel.se)
   ├── rate_limit on /keykeep/psono/authentication/{prelogin,login,register}*
   └── reverse_proxy → Odoo
        ▼
Odoo http.Controller  /keykeep/psono/*
   ├── /info/                 signed TOFU info (Ed25519)
   ├── /authentication/       prelogin, login (Box exchange), register,
   │                          verify-email, activate-token, logout
   ├── /user/status/          status polling
   ├── /datastore/            list (GET), create (PUT), update (POST), detail
   ├── /secret/               create (PUT), update (POST), read (GET <id>/)
   ├── /secret/history/<id>/  version history
   ├── /bulk-secret/          bulk create (used by import)
   ├── /share/right/          {"share_rights": []} (MVP)
   └── /avatar/               {"avatars": []} (MVP)

Models: keykeep.psono.user/token/datastore/secret/secret.history/access.log
Crypto: crypto.py (PyNaCl SecretBox/Box/SigningKey) + bcrypt (authkey)
Keys:   server identity keypair — odoo.conf params (pillar) or
        /var/lib/odoo/keykeep_psono_keys.conf (auto-generated, mode 600)
```

## Wire format (psono contract)

- All authenticated request bodies and responses are SecretBox-encrypted
  `{text: hex, nonce: hex}` (24-byte nonce, XSalsa20-Poly1305).
- The client adds the `{"data": ...}` wrapper itself — the server must NOT
  double-wrap (breaks clients with UNENCRYPTED_RESPONSE_RECEIVED).
- Login uses Box key exchange; `/info/` is Ed25519-signed (TOFU verify_key).
- Replay protection: `Authorization-Validator` header (encrypted request_time +
  device fingerprint); token deleted on mismatch.

## Deployment (Salt)

`/usr/share/odoo-keykeep/salt/keykeep_psono/init.sls` — installs/upgrades the
module on the ledningssystem minion, optionally pins keys via pillar.

Manual install:

```bash
sudo checkmodule -d ledningssystem -m keykeep_psono
```

## Server identity keys — BACKUP REQUIREMENT

The server identity keypair signs `/info/` (TOFU fingerprint clients approve)
and performs the login Box exchange. The private key lives either in
`/etc/odoo/odoo.conf` (`keykeep_psono_private_key` / `keykeep_psono_public_key`,
managed via Salt pillar) or the auto-generated
`/var/lib/odoo/keykeep_psono_keys.conf` (mode 600).

**Back up the keys together with the database.** Rotating the keys makes all
clients re-approve the server (TOFU) and invalidates the login exchange.

## Import / export

Import and export run entirely in the browser (psono-web):
- **Import:** Firefox (CSV), Bitwarden/Vaultwarden (JSON, unencrypted),
  KeePass.info (CSV/XML), KeePassXC, Chrome, 1Password, LastPass, Dashlane,
  Enpass, Proton Pass, Safari, Nextcloud, ... (17+ formats).
- **Export:** JSON, CSV, KeePass (kdbx, password-protected).

Zero-knowledge: import sends only encrypted secrets via `/bulk-secret/`;
export decrypts locally and downloads the file (no server request, not
auditable server-side). Imports are audited in `keykeep.psono.access.log`
(format + count, never content).

## Personal Vault tab (My Profile)

The `res.users` form has a "Personal Vault" page: registration/verification
status, "Open Vault" (→ psono-web), and deep links to import/export
(`#/other/import`, `#/other/export`).

## Monitoring (Zabbix)

- HTTP check: `GET https://ledningssystem.vertel.se/keykeep/psono/info/` → 200
- Certificate age (Let's Encrypt via Caddy)
- Odoo service status (existing)

## Tests

```bash
cd /usr/share/odoo-keykeep
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <testdb> \
  --test-enable --update keykeep_psono --stop-after-init \
  --http-port 8098 --addons-path "$(grep '^addons_path' /etc/odoo/odoo.conf | cut -d= -f2)"
```

9 unit tests: crypto round-trips + wire shape, token hash (never clear key),
history auto-snapshot, 1:1 user constraint, res_users vault status.

Conformance client (full protocol against a live instance):
`/tmp/psono-spike/conformance_client.py` — info → prelogin → login → activate
→ datastore/secret CRUD → history → logout.
