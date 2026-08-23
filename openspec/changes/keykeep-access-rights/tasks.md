# Tasks: Keykeep Access Rights

> Referenser: specs/access-rights (delta), design.md. Systern i
> /home/waland/plan/odoo-saltstack (change minion-overview, tasks 4.5–4.7)
> trackar leveransen — markera klart där också.

## 1. Meny & verifiering (keykeep)

- [ ] 1.1 Add `groups="keykeep.group_user"` to `menu_keykeep_root` in
      `keykeep/views/keykeep_menu.xml`; verify `menu_keykeep_config` keeps
      `groups="keykeep.group_manager"`
- [ ] 1.2 Verify `base.group_system` implied Keykeep Admin still present
      (`keykeep/security/keykeep_security.xml`) — no code change expected

## 2. Team-rätt — partner-scopad credential-visning (keykeep + bifrost_keykeep)

- [ ] 2.1 Add read-access check on the current `res.partner` in the partner
      smart-button actions (`action_view_provider_credentials` and friends in
      `bifrost_keykeep/models/res_partner.py`)
- [ ] 2.2 Scope the returned credentials to that partner's subscription
      (reuse `_bifrost_credentials()`); do NOT add global credential read
      for Keykeep User; do NOT lower Manager/DevOps/Admin rights
- [ ] 2.3 Decide at implementation: `action_add_api_key`/`action_add_credential`
      stay group-gated (Manager+) or follow partner-read; default is group-gated
- [ ] 2.4 Keep existing record rules (company-based) intact; verify they still
      apply after the scoped methods

## 3. Kvalitet & deploy

- [ ] 3.1 Tests: menu hidden without Keykeep User; Settings user is Keykeep
      Admin; partner reader sees only that partner's credentials; Keykeep
      User has no global credential read; existing rights unchanged
- [ ] 3.2 Bump versions (`keykeep`, `bifrost_keykeep`) and upgrade with
      `--update`
- [ ] 3.3 Report completion back to syster-change `minion-overview`
      (odoo-saltstack tasks 4.5, 4.6, 4.7)
