## Why

Keykeep idag är en subscription manager med en inbyggd — men rudimentär — credential-lagring. Credentials saknar versionshistorik, åtkomstloggning, miljöstöd och en dedikerad användarupplevelse. Det gör att två separata målgrupper (ekonomi och drift) tvingas in i samma gränssnitt utan anpassning, och att hemligheter hanteras utan spårbarhet — en compliance-risk.

## What Changes

- **Ny Dashboard**: Första anhalten med widgets som anpassas efter användarens roll — ekonomi ser kostnader/förnyelser, drift ser credential health/audit.
- **Credential-versioning**: Varje ändring av en hemlighet skapar en versionspost. Möjliggör historik och rollback.
- **Credential-environments**: Stöd för production/staging/development/testing per credential. Unik constraint utökas till (name, subscription_id, environment).
- **Åtkomstloggning (audit)**: Varje reveal av en hemlighet loggas — vem, när, vad, IP. Synlig i UI och exportbar.
- **Ny devops-grupp**: Separat behörighetsgrupp som kan se och avslöja hemligheter men inte se kostnader eller redigera prenumerationer.
- **Omdesignat credential-UI**: Ny wizard för att skapa credentials, omarbetad reveal-dialog med varning och auto-stängning, fristående credential-vy med filter, samt omdesignad credentials-tab i subscription-formuläret med kortvy per miljö.
- **Rotation health**: Spårning av hur länge sedan en credential senast roterades, med varningar för inaktuella.

## Capabilities

### New Capabilities

- `credential-lifecycle`: Miljöstöd (production/staging/development/testing), versionshistorik med möjlighet att se tidigare värden, spårning av rotationsålder, och credential expiry-kopplingar till subscription-status. Nya modeller: `keykeep.credential.version`, nytt fält `environment` på `keykeep.credential`.
- `credential-audit`: Åtkomstloggning vid reveal av credentials. Ny modell `keykeep.credential.access.log`. Loggar användare, tidpunkt, IP-adress, åtgärdstyp och vilka fält som exponerades. Synlig i credential-vyn och i en separat audit-rapport.
- `keykeep-dashboard`: Dashboard-sida som är adaptive per användarroll. Widgets: kostnadsöversikt, credential health, kommande förnyelser, senaste aktivitet, kostnadsgraf, snabbåtgärder. Widgets visas/göms baserat på användarens grupper.
- `credential-management`: Omdesignat UI för att skapa och hantera credentials. Wizard i steg (vad → hemlighet → detaljer). Ny reveal-dialog med audit-varning, auto-stängning och copy-knapp. Fristående credential-vy med environment-filter. Omdesignad credentials-tab i subscription-formulär med kortvy per miljö.

### Modified Capabilities

- (inga — detta är första versionen med specifikationer)

## Impact

- **Databas**: Nya tabeller `keykeep_credential_version` och `keykeep_credential_access_log`. Ny kolumn `environment` på `keykeep_credential`. Ändrad unique constraint på `keykeep_credential`.
- **Säkerhet**: Ny grupp `group_devops`. Omarbetade ACL-regler för att separera ekonomi- och drift-behörigheter.
- **Views**: Nya XML-filer för dashboard, credential-kanban, credential-wizard, audit-logg. Uppdateringar av subscription-form, credential-form, meny.
- **Assets**: Uppdaterad SCSS för environments, status-badges, dashboard-widgets. Ny JS för auto-stängning, copy-funktion, reveal-flöde.
- **Python**: Nya modeller (version, access.log). Utökad credential-modell (environment, rotation tracking). Utökad subscription-modell (credential health-kopplingar).
- **Bakåtkompatibilitet**: Alla existerande credentials får `environment = 'production'` vid migrering. Nuvarande reveal-beteende ersätts med loggat flöde — **BREAKING** för den som förlitar sig på att reveals är ospårbara.
