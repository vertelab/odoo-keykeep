# Proposal: Keykeep Access Rights — meny, admin-automatik och team-rätt

## Why

Keykeep-menyn är idag synlig för alla interna användare (rotmenyn saknar
gruppbegränsning) och Keykeep User (lägsta nivån) kan inte se API-nycklar/
credentials för en partner via smartknapparna på `res.partner` — team som
har rätt att se en partner skall också se den partnerns nycklar. Samtidigt
ska Odoo-administratörer automatiskt vara Keykeep-admins (redan implementerat
— verifieras här).

## What Changes

- **Meny-synlighet kräver Keykeep User**: `menu_keykeep_root` får
  `groups="keykeep.group_user"` så Keykeep-menyn (inkl. undermenyer) bara
  syns för medlemmar i lägsta nivån. Ingen automatisk synlighet för interna
  användare. Config-undermenyn förblir Manager-gated.
- **Admin-automatik (verifieras)**: `base.group_system` implicerar redan
  Keykeep Admin — bekräftas i spec/scenarier, ingen kodändring förväntas.
- **Team-rätt för partner-credentials**: smartknapparna för API-key och
  credential på `res.partner` skall fungera för alla som kan läsa den
  partnern — de ser den partnerns nycklar/credentials (scopat), utan att få
  global läsrätt på `keykeep.credential`. Befintliga rättigheter för
  Manager/DevOps/Admin sänks INTE.
- **Access Rights-rubrik (verifieras)**: grupperna ligger redan under egen
  kategori "Keykeep" — bekräftas.

## Capabilities

### New Capabilities
- `access-rights`: Keykeep access-modell — meny-synlighet, admin-automatik
  och partner-scopad credential-visning.

### Modified Capabilities
- _Inga._ Befintliga specs (credential-management, credential-audit) berörs
  inte av dessa krav.

## Impact

- **Moduler**: `keykeep` (views/keykeep_menu.xml, security/keykeep_security.xml),
  `bifrost_keykeep` (views/res_partner_views.xml, models/res_partner.py —
  smartknapparna). Båda får version bump vid behov.
- **Syster-repo**: denna change är syster till `minion-overview` i
  /home/waland/plan/odoo-saltstack (tasks 4.5–4.7) — leveransen trackas
  därifrån; inga spec-ändringar där behövs utöver att tasks refererar hit.
- **Säkerhet**: ingen global credential-läs för Keykeep User; partner-scopad
  visning via action-metoder med läsrätts-koll; befintliga record rules
  (company-baserade) behålls.
