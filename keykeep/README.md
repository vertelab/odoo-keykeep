# Keykeep — Credential Management

Keykeep lagrar tjänstecredentials (API-nycklar, tokens, lösenord) krypterat med
per-credential Fernet-nycklar, wrappade av en master-nyckel från Odoo-konfigurationen.

## Installation & master-nyckel (keykeep_encryption_key)

Master-nyckeln läses från **odoo.conf** (env/config), ALDRIG från databasen:

```ini
[options]
keykeep_encryption_key = <Fernet key>
```

Generera en nyckel:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Utan `keykeep_encryption_key` i odoo.conf blockerar modulen alla credential-operationer
med ett tydligt fel — det finns ingen auto-generering i DB längre.

### Salt-pillar

Eftersom odoo.conf är Salt-managed på ledningssystemet ska nyckeln levereras via
pillar (t.ex. `odoo:config:keykeep_encryption_key`) till odoo.conf. Se
`odoo/*.sls`-staten på Salt-mastern. Nyckeln får INTE hamna i en repo eller i
ir.config_parameter.

## Migration (18.0.1.1.0 → 18.0.1.2.0) — hardening

Moduluppgraderingen kör `migrations/18.0.1.2.0/pre-migrate.py` som:

1. Verifierar att `keykeep_encryption_key` finns i odoo.conf (avbryter annars med instruktion)
2. För varje credential utan `secret_key`: skapar per-credential nyckel (wrappad av master)
3. Migrerar legacy-värden från `ir.config_parameter` (`keykeep.encryption_key`,
   `keykeep_credential_<id>_password`, `keykeep_credential_<id>_key_value`) till
   kolumnerna `password_cipher`/`key_value_cipher`
4. Omskrypterar versions-snapshots till respektive credential-nyckel
5. Raderar legacy config-params efter framgång

Skriptet är **idempotent** — körs bara för credentials som saknar `secret_key`.

### BREAKING: read-vägen

- `read()` på `keykeep.credential` returnerar **chiffertext**, aldrig plaintext
- Plaintext fås bara via explicita, audit-loggade actions:
  - `action_reveal_password` / `action_copy_credential` (UI, `reveal`/`copy` i access-log)
  - `_read_encrypted(field, system=True)` — systemväg för integrationer (loggar `system_read`)
- Alla integrationer (t.ex. bifrost_keykeep) MÅSTE använda systemvägen

## Retention

- Access-loggar: `keykeep.access_log_retention_days` (default 730), daglig cron
  "Keykeep: Cleanup Old Access Logs"
- Versions-snapshots: `keykeep.credential_version_retention` (default 10), daglig cron
  "Keykeep: Purge Old Credential Versions" — purgen loggas per credential

## Record rules

- Manager/devops: ser bara credentials inom eget företag (subscription.company_id)
- Admin: global åtkomst
- Versioner + access-log följer credentialns scope via stored `company_id`
