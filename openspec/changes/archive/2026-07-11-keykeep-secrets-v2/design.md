## Context

Keykeep är en Odoo 18-modul (Alpha-status) som hanterar SaaS-prenumerationer. Den har en inbyggd credential-modell (`keykeep.credential`) som krypterar lösenord/API-nycklar med Fernet-kryptering (primär) eller OCA `data_encryption` (fallback), lagrat i `ir.config_parameter`. Credentials är kopplade 1:N till prenumerationer.

**Nuvarande begränsningar:**
- Ingen versionshistorik — ändringar skriver över tidigare värden permanent
- Ingen åtkomstloggning — reveals är ospårbara
- Inga miljöer — en credential per typ och prenumeration
- Credentials är en inline-lista i subscription-formuläret — ingen egen vy
- 3 grupper (user/manager/admin) utan separation mellan ekonomi- och drift-behörigheter
- Ingen dashboard

**Intressenter:** Två personas — ekonomi (ser kostnader, förnyelser) och drift (ser hemligheter, miljöer). Admin ser allt.

## Goals / Non-Goals

**Goals:**
- Credential-versioning där varje ändring bevaras och är läsbar
- Åtkomstloggning vid reveal med användare, tidpunkt, IP
- Miljöstöd (production/staging/development/testing) per credential
- Dashboard som adaptive visar rätt information per användarroll
- Separat behörighet för drift-personal (se hemligheter, inte kostnader)
- Omdesignat credential-UI: wizard för skapande, ny reveal-dialog, fristående credential-vy

**Non-Goals:**
- Runtime secret injection (CLI, SDK, K8s operator) — detta är Infisical/Vaults domän
- PKI/certifikathantering — credential_type "certificate" förblir ett textfält
- Automatisk secret rotation — för komplext för v1, manuell rotation med versionsspårning räcker
- PAM (just-in-time access, sessionsinspelning)
- Integration med externa secrets managers (infisical/vault) — kan komma i v3

## Decisions

### 1. Versioning: separat tabell, inte JSON-fält

**Val:** `keykeep.credential.version` som separat SQL-tabell.

**Alternativ:** JSON-fält på `keykeep.credential` med versionsarray.

**Motivering:** Separat tabell ger indexerbar historik, enkel SQL-frågning ("visa alla versioner av credential 42"), och möjlighet att soft-deleta credentials men bevara versionshistorik. JSON hade varit enklare men sämre för frågor och compliance.

**Modell:**
```
keykeep.credential.version
├── credential_id (Many2one → keykeep.credential)
├── version_number (Integer, auto-increment per credential)
├── username (Char, snapshot)
├── password (Text, encrypted snapshot)
├── key_value (Text, encrypted snapshot)
├── changed_by (Many2one → res.users)
├── changed_at (Datetime)
└── change_note (Char)
```

### 2. Kryptering av versionsposter: samma Fernet-nyckel som aktuell credential

**Val:** Återanvänd samma krypteringsinfrastruktur (`_get_fernet_cipher()` / `_store_encrypted()`) för att kryptera versionsposternas `password` och `key_value`.

**Alternativ:** Separat "master key" per credential. OAEP-hölje med per-version IV.

**Motivering:** Samma nyckel är enklast att implementera och underhålla. Risk: om Fernet-nyckeln roteras måste alla versioner omkrypteras — men detta är ett generellt problem som löses när/om nyckelrotation implementeras, inte unikt för versioning.

**Lagringsstrategi för versioner:** `ir.config_parameter` med nycklar på formatet `keykeep_credential_{id}_v{version}_{field}`. Detta undviker att blanda versioner med aktuella värden som använder `keykeep_credential_{id}_{field}`.

### 3. Åtkomstlogg: synkron skrivning före reveal

**Val:** `keykeep.credential.access.log` skapas synkront i `action_reveal_password()` **innan** värdet visas.

**Alternativ:** Asynkron loggning via queue/job. Loggning efter reveal (risk att användaren hinner se värdet innan loggen skrivs).

**Motivering:** Synkron loggning garanterar att åtkomsten är loggad innan hemligheten exponeras. Om loggningen misslyckas ska reveal blockeras. Detta är viktigt för compliance — man ska aldrig kunna se en hemlighet utan att det loggas.

**Modell:**
```
keykeep.credential.access.log
├── credential_id (Many2one → keykeep.credential)
├── user_id (Many2one → res.users)
├── action (Selection: reveal/copy/rotate/view_metadata)
├── fields_accessed (Selection: password/key_value/both)
├── ip_address (Char)
├── accessed_at (Datetime)
└── subscription_id (Many2one, related via credential_id, store=True)
```

### 4. Miljöer: fält på credential, utökad unik constraint

**Val:** `environment` som Selection-fält på `keykeep.credential` med värden `production`, `staging`, `development`, `testing`. Unik constraint ändras från `(name, subscription_id)` till `(name, subscription_id, environment)`.

**Alternativ:** Separat modell `keykeep.environment` med Many2one. Miljö som taggar (Many2many).

**Motivering:** Fyra fasta miljöer täcker 95% av användningsfall. Selection är enklare att filtrera och gruppera på än en separat modell. Kan utökas till custom-värden senare via `selection_add` om behov uppstår.

**Migrering:** Alla existerande credentials får `environment = 'production'` via migreringsscript (SQL eller Python vid moduluppgradering).

### 5. Behörighetsmodell: ny devops-grupp, omarbetade ACLs

**Val:** Lägg till `group_devops` som ärver `group_user` men INTE `group_manager`. Ge `group_devops` läs/skriv på `keykeep.credential` och `keykeep.credential.version` men INTE på `cost_amount`, `currency_id`, `invoice_ids` etc. på subscription.

**Nuvarande hierarki:**
```
group_user → group_manager → group_admin
```

**Ny hierarki:**
```
group_user ─┬─ group_manager ──── group_admin
            │
            └─ group_devops ───── (parallell gren)
```

**ACL-ändringar:**
- `group_devops`: Kan läsa subscription (metadata), kan INTE läsa `cost_amount`, `currency_id`, `invoice_ids`. Kan skapa/redigera/avslöja credentials. Kan se versionshistorik och åtkomstlogg.
- `group_manager`: Kan INTE avslöja credentials (reveal flyttas från `group_admin` till `group_devops` och `group_admin`).
- `group_admin`: Oförändrad — ser allt.

### 6. Dashboard: Odoo enterprise-style widgets med treshold-baserad synlighet

**Val:** En dashboard-sida implementerad som en `ir.ui.view` med `kanban`- eller `form`-vy, där widgets är Odoo QWeb-templates med `groups`-attribut för synlighet.

**Alternativ:** Owl-komponent (kräver modern Odoo JS-stack). Enterprise web studio dashboard.

**Motivering:** QWeb + `groups` är native Odoo, kräver ingen JS-omkompilering, och fungerar med befintlig infrastruktur. Widgets är permission-gated via `groups="keykeep.group_manager"` etc. Komplexiteten i Owl är inte motiverad för en dashboard med statiska widgets.

### 8. Tidigare versionsvärden: dekrypterbara med loggning

**Val:** Användare med reveal-behörighet kan se dekrypterade tidigare versionsvärden. Varje reveal av ett historiskt värde loggas som `action = 'reveal_version'`.

**Alternativ:** Endast metadata (vem, när, notering) — inga historiska värden visas.

**Motivering:** Om en credential läcker och måste roteras akut, behöver drift-personal kunna verifiera att det gamla värdet faktiskt var det som läckte. Utan synliga historiska värden är versioning bara en logg utan praktiskt värde för incident response. Samma audit-loggningskrav gäller för historiska reveals som för aktuella.

### 9. Access log auto-cleanup: daglig cron, 2 års retention

**Val:** En daglig cron (`_cron_cleanup_access_logs`) raderar access.log-poster äldre än 2 år.

**Alternativ:** Manuell cleanup. Ingen cleanup (obegränsad retention).

**Motivering:** 2 år täcker de flesta compliance-krav (bokföring, GDPR-relaterad spårbarhet) utan att tabellen växer ohämmat. För organisationer med längre krav kan parametern `keykeep.access_log_retention_days` (default 730) justeras.

### 10. Credential-wizard: multi-step wizard, inte inline-editing

**Val:** Ny wizard-modell (`keykeep.credential.create.wizard`) med stegvis input: steg 1 (vad + miljö), steg 2 (hemligheten), steg 3 (detaljer).

**Alternativ:** Fortsätta med inline-editable list. Single-page form.

**Motivering:** Wizard ger fokuserad upplevelse, validering per steg, och möjlighet att visa kontextuell hjälp (auto-detect av nyckeltyp, lösenordsgenerator). Inline-editing fungerar för enkla fält men credentials är säkerhetskritiska och förtjänar en dedikerad vy.

## Risks / Trade-offs

- **[Risk] Fernet-nyckelrotation kräver omkryptering av alla versioner** → Mitigation: Dokumentera att nyckelrotation är en manuell process som kräver omkryptering. Bygg en `_reencrypt_all_versions()`-metod för framtida bruk. Inte ett problem för v1 eftersom nyckelrotation inte implementeras.

- **[Risk] Synkron åtkomstloggning kan göra reveal långsammare** → Mitigation: Åtkomstloggen är en enkel INSERT — millisekunder. Ingen mätbar påverkan för användaren. Om problem uppstår kan `access_log`-tabellen partitioneras per månad.

- **[Risk] Unik constraint-ändring kan krocka med existerande data** → Mitigation: Migreringsscript sätter `environment = 'production'` på alla existerande rader innan constrainten appliceras. Om det finns duplicerade (name, subscription_id) i dagsläget (pga. att constrainten inte täcker environment än), hanteras de genom att appendera miljönamn till name.

- **[Risk] group_devops kan se subscriptions men inte kostnader — Odoos record rules är oflexibla** → Mitigation: Använd `groups` på fältnivå i vyn (`groups="keykeep.group_manager"` på kostnadsfält). För list-vyer där devops ser subscription: använd en separat tree view utan kostnadskolumner, styrd av `groups` på `<record>`-nivå.

- **[Trade-off] Dashboard i QWeb vs Owl** → QWeb är enklare men mindre interaktivt. För v1 räcker QWeb med `groups`-baserad widget-synlighet. Owl kan övervägas vid behov av realtidsuppdateringar.

## Migration Plan

1. `keykeep` moduluppgradering (`-u keykeep`)
2. Python-migreringshook i `__manifest__.py` (`pre_init_hook` eller migrationsscript i `migrations/18.0.1.1.0/`)
3. Migreringssteg:
   a. Lägg till `environment`-kolumn med default `production`
   b. Ta bort gamla unique constraint `(name, subscription_id)`
   c. Lägg till ny unique constraint `(name, subscription_id, environment)`
   d. Skapa `keykeep_credential_version` och `keykeep_credential_access_log` tabeller
   e. Skapa `group_devops` grupp
4. Rollback: `environment`-kolumn kan droppas, gamla constrainten återställas. Versioner och access logs kan droppas utan dataförlust (förutom audit-historiken i sig).

## Resolved Questions

- **Q1:** Auto-cleanup av access logs: ✅ Ja, en daglig cron rensar `keykeep.credential.access.log`-poster äldre än 2 år. Bevarar tillräckligt för compliance utan att tabellen växer ohämmat.
- **Q2:** Konfigurerbar auto-stängningstid: ✅ Ja, default 60 sekunder, konfigurerbart via systemparametern `keykeep.reveal_timeout_seconds`. Värde 0 = ingen auto-stängning.
- **Q3:** `group_devops` tillgång till cost_forecast/invoice_stub: ✅ Nej — devops ska inte se finansiell data. Endast `group_manager` och `group_admin`.
- **Q4:** Tidigare versionsvärden ska vara dekrypterbara: ✅ Ja — användare med reveal-behörighet (`group_devops` eller `group_admin`) kan se dekrypterade tidigare versionsvärden i versionshistoriken. Samma åtkomstloggning gäller: varje gång ett tidigare versionvärde visas loggas det som en access med `action = 'reveal_version'`.
