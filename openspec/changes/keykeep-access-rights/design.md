# Design: Keykeep Access Rights

## Context

Verifierat i produktion (ledningssystem-databasen): `menu_keykeep_root` har
ingen gruppbegränsning (synlig för alla interna); `menu_keykeep_config` är
redan Manager-gated; `base.group_system` implicerar Keykeep Admin
(keykeep/security/keykeep_security.xml, samma mönster som ai_agent_core);
Keykeep-grupperna ligger under egen kategori "Keykeep" (id 298); Keykeep User
har ingen läsrätt på `keykeep.credential`/`keykeep.credential.reveal`
(Manager: CRUD, DevOps: CRUD + reveal-läs, Admin: allt).

## Goals / Non-Goals

**Goals**: Lås Keykeep-menyn vid lägsta nivå; verifiera admin-automatik +
egen rubrik; gör partner-credentials synliga för partner-läsare utan global
läsrätt.

**Non-Goals**: Ingen ändring av Manager/DevOps/Admin-rättigheterna. Ingen
ändring av reveal-loggning (credential-audit). Ingen global credential-läs
för Keykeep User.

## Decisions

### D1: Meny-låsning på rotmenyn
**Beslut**: `menu_keykeep_root` får `groups="keykeep.group_user"` i
`keykeep/views/keykeep_menu.xml`. Odoo döljer barnmenyer när föräldern är
dold, så rot-restriktionen räcker; `menu_keykeep_config` behåller sin
`groups="keykeep.group_manager"`.

**Alternativ**: lägga groups på varje undermeny — förkastat (dubbelt arbete,
rot-regeln räcker och blir enda sanningskälla).

### D2: Admin-automatik — verifiering, ingen kodändring
**Beslut**: `base.group_system` implicerar redan Keykeep Admin
(keykeep_security.xml `<record id="base.group_system">`). Kravet fångas som
spec-scenario och verifieras i test; ingen ny XML behövs.

### D3: Team-rätt via scopad action-metod, inte record rule
**Beslut**: Smartknapparna för API-key/credential på `res.partner`
(bifrost_keykeep: `action_view_provider_credentials`, `action_add_api_key`,
`action_add_credential` i models/res_partner.py) får läsrätts-koll på den
aktuella partnern och returnerar/skapar bara credentials knutna till den
partnerns subscription (`partner._bifrost_credentials()` — befintlig
metod). Ingen ny modell-access för Keykeep User; Manager/DevOps/Admin
lämnas orörda; befintliga company-baserade record rules
(`rule_credential_manager_company` m.fl.) fortsätter gälla.

**Alternativ**: record rule på `keykeep.credential` "synlig om partnern är
läsbar" — dynamisk partner-läsbarhet är svår att uttrycka i en statisk
domain; scopad metod är säkrare och testbar.

## Risks / Trade-offs

| Risk | Nivå | Mitigering |
|---|---|---|
| Team-rätt läcker utanför partner | Medel | Action-metod kontrollerar partner-läsrätt; returnerar bara den partnerns credentials; inga globala rättigheter |
| Meny-låsning överraskar användare | Låg | Admins ser allt via base.group_system; kommunicera ändringen |
| Bifrost_keykeep-bryggan ändras men keykeep-specen äger kravet | Låg | Tasks refererar båda modulerna; syster-change i odoo-saltstack trackar leveransen |

## Migration Plan

1. Version bump: `keykeep` (om meny/security ändras), `bifrost_keykeep`.
2. Deploy till /usr/share/odoo-keykeep + /usr/share/odoo-bifrost,
   uppgradera med `--update`.
3. Verifiera: Keykeep-menyn dold utan grupp; Settings-användare ser allt;
   partner-läsare ser partnerns credentials; Keykeep User saknar global
   credential-läs.
4. Rollback: återdeploya föregående version; meny-groups tas bort, scopad
   metod återgår.

## Open Questions

- Ska `action_add_api_key`/`action_add_credential` (skapa) också vara öppna
  för partner-läsare, eller bara visning (`action_view_provider_credentials`)?
  (Specen säger "view"; skapa kan kräva Manager+. Avgör vid implementering
  utan att ändra spec — förslaget är att skapa förblir grupp-gated.)
