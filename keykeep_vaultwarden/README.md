# Keykeep Vaultwarden Bridge

Additiv brygga: när Vaultwarden är konfigurerad lagras keykeep-credential-värden
som Bitwarden-items i valvet i stället för i keykeep-kolumnerna. Anropare
(reveal-wizard, bifrost_keykeep) märker inget — backend-valet är transparent.

**Autonomi:** keykeep fungerar identiskt utan denna modul installerad eller
konfigurerad (intern Fernet-backend är default).

## Installation

Lägg till `keykeep_vaultwarden` i addons_path och installera modulen.
Ingen hård dependency på `bitwarden-sdk` — SDK:n lazy-importas i try/except.

## Konfiguration

1. Skapa en `keykeep.vaultwarden.backend` (Settings → Keykeep → Vaultwarden):
   - **Vault URL** — måste börja med `https://`
   - **Token reference** — env-nyckelnamn (default `keykeep_vaultwarden_token`);
     själva token levereras via odoo.conf env/pillar, ALDRIG i DB
   - **Collection** — valvkollektion där keykeep-items lagras (default "Keykeep")
2. Lägg token i odoo.conf:

   ```ini
   [options]
   keykeep_vaultwarden_token = <org access token>
   ```

3. Aktivera backend: sätt `active=True` på backend-posten.

## Driftlägen

| Backend | När | Lagring |
|---|---|---|
| intern (default) | ingen backend konfigurerad | Fernet i `password_cipher`/`key_value_cipher`-kolumner |
| vault | backend konfigurerad + aktiv | Bitwarden-item per credential (`vault_item_id` på credential) |

Bytet sker per credential via `action_switch_backend(to_vault=True/False)` (batch).
Växlingen: läser plaintext via nuvarande backend (system-read, audit-loggad),
skriver till mål-backend, raderar från källan, loggar `backend_switch` i access-loggen.
Misslyckade credentials rapporteras en i taget — inga tysta fel.

**OBS (spike-status):** Vault-item-operationerna (store/read/delete) kräver
bitwarden-sdk för org-key-kryptering och är markerade som spike-pending i
`keykeep_vaultwarden_backend.py` (höjer tydligt UserError tills SDK-stödet är på plats).
Health-check (`GET /alive`) och token-auth-primitiver fungerar redan.

## Offline-beteende

- Valvet onåbart vid reveal/system-read → tydligt felmeddelande
- Metadata (namn, typ, expiry, versions-räkning) förblir läsbar — bara värdena kräver valvet

## Vaultwarden-krav

- Organisation med collection ("Keykeep")
- Org access token med cipher-rättigheter för kollektionen
- HTTPS-endpoint (valideras vid konfigurering)
