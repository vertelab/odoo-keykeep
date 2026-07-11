## 1. Data Model & Migration

- [x] 1.1 Add `environment` Selection field to `keykeep.credential` model
- [x] 1.2 Create `keykeep.credential.version` model with fields: credential_id, version_number, username, password, key_value, changed_by, changed_at, change_note
- [x] 1.3 Create `keykeep.credential.access.log` model with fields: credential_id, user_id, action, fields_accessed, ip_address, accessed_at, subscription_id (related)
- [x] 1.4 Update unique constraint on `keykeep.credential` from `(name, subscription_id)` to `(name, subscription_id, environment)`
- [x] 1.5 Add security record rules for new models (ir.model.access.csv)
- [x] 1.6 Write migration script: set `environment = 'production'` on all existing credentials, handle duplicate name+subscription pairs
- [x] 1.7 Update `__manifest__.py` version to `18.0.1.1.0` and bump `development_status` if appropriate

## 2. Security & RBAC

- [x] 2.1 Create `group_devops` security group in `keykeep_security.xml` — inherits `group_user`, NOT `group_manager`
- [x] 2.2 Update ACLs: `group_devops` gets read/write on `keykeep.credential`, `keykeep.credential.version`, `keykeep.credential.access.log`
- [x] 2.3 Restrict `group_manager` from revealing credentials (move reveal button `groups` from `group_admin` to `group_devops,group_admin`)
- [x] 2.4 Add field-level `groups` on subscription views to hide `cost_amount`, `currency_id`, `invoice_ids` from `group_devops`
- [x] 2.5 Create separate subscription tree view for `group_devops` without financial columns
- [x] 2.6 Update `keykeep.credential.reveal` wizard access check to allow `group_devops`

## 3. Credential Lifecycle — Versioning & Environments

- [x] 3.1 Implement `_create_version()` method on `keykeep.credential` — encrypts and stores snapshot on create and write of password/key_value/username
- [x] 3.2 Modify `create()` and `write()` on `keykeep.credential` to call `_create_version()` after super
- [x] 3.3 Add `version_count` and `latest_version` computed fields on `keykeep.credential`
- [x] 3.4 Add `rotation_age` computed field (days since last `write_date`) on `keykeep.credential`
- [x] 3.5 Implement `_cron_check_credential_rotation()` — daily cron that posts warnings for credentials with rotation_age > 90
- [x] 3.6 Register `_cron_check_credential_rotation` and `_cron_cleanup_access_logs` in `data/ir_cron_data.xml`
- [x] 3.7 Extend `_cron_check_credential_expiry()` to update subscription `kanban_state` when credentials expire
- [x] 3.8 Add `_compute_kanban_state` logic in `keykeep.subscription` to factor in credential expiry and rotation health
- [x] 3.9 Add version history view (tree/list) inside credential form
- [x] 3.10 Implement `_reencrypt_all_versions()` utility method for future key rotation (not called yet, but available)
- [x] 3.11 Implement historical version reveal: `action_reveal_version()` method that decrypts and logs `reveal_version` action
- [x] 3.12 Add reveal buttons on version history list items for users with `group_devops` or `group_admin`

## 4. Credential Audit

- [x] 4.1 Implement `_log_access()` method on `keykeep.credential` — creates `access.log` entry with user, action, fields, IP
- [x] 4.2 Modify `action_reveal_password()` to call `_log_access()` BEFORE decrypting — fail if log creation fails
- [x] 4.3 Add access log tab/section in credential form view
- [x] 4.4 Create audit report action and menu item (Reports → Audit Log)
- [x] 4.5 Create audit log tree view with filters (by user, by subscription, by date range, by action)
- [x] 4.6 Add `action` field options: reveal, copy, rotate, view_metadata, reveal_version
- [x] 4.7 Implement `_cron_cleanup_access_logs()` — daily cron that deletes entries older than `keykeep.access_log_retention_days` (default 730)
- [x] 4.8 Add system parameter `keykeep.access_log_retention_days` with default 730

## 5. Dashboard

- [x] 5.1 Create `keykeep_dashboard.xml` view — dashboard template using form view with widget divs
- [x] 5.2 Implement cost summary widget: sum of active subscription costs, month-over-month change
- [x] 5.3 Implement subscription health widget: active count, renewals within 30 days, overdue count
- [x] 5.4 Implement credential health widget: healthy/warning/expired counts, stale rotation count
- [x] 5.5 Implement upcoming renewals widget: next 5 subscriptions by `next_renewal_date`
- [x] 5.6 Implement recent activity widget: last 10 access log entries
- [x] 5.7 Implement cost forecast chart widget: monthly projections 6 months ahead, grouped by category
- [x] 5.8 Implement quick actions widget: context-sensitive action buttons
- [x] 5.9 Add `groups` attribute to each widget for persona-based visibility
- [x] 5.10 Add dashboard menu item as first entry under Keykeep root menu
- [x] 5.11 Add dashboard SCSS styles: widget cards, status colors, chart colors

## 6. Credential Management UI

- [x] 6.1 Create `keykeep.credential.create.wizard` model with fields for each wizard step
- [x] 6.2 Create wizard view XML — 3 steps with conditional field visibility per credential_type
- [x] 6.3 Implement key type auto-detection in wizard: Stripe (`sk_`), GitHub (`ghp_`), Sentry, AWS patterns
- [x] 6.4 Implement password generator utility — generate strong 16+ char password, show once in field
- [x] 6.5 Create standalone credential tree view with columns: name, subscription, environment, type, status, expiry, last accessed
- [x] 6.6 Create credential kanban view grouped by environment
- [x] 6.7 Create credential search view with filters: by environment, by status (expiring/expired/stale), by type, by subscription
- [x] 6.8 Add "Credentials" menu item between Dashboard and Subscriptions
- [x] 6.9 Add credential count badge and health summary to subscription kanban cards
- [x] 6.10 Redesign credentials tab in subscription form: card layout grouped by environment
- [x] 6.11 Add action buttons on credential cards: Reveal, Copy, Edit
- [x] 6.12 Add rotation health warning banner in credentials tab when stale rotations exist

## 7. Reveal Dialog Redesign

- [x] 7.1 Redesign `credential_reveal` wizard view: audit warning section, credential context, value display area
- [x] 7.2 Add copy-to-clipboard button with JavaScript handler and "Copied!" confirmation
- [x] 7.3 Add auto-close countdown timer with configurable timeout from system parameter `keykeep.reveal_timeout_seconds` (default 60s)
- [x] 7.4 Add system parameter `keykeep.reveal_timeout_seconds` with default 60 (0 = disabled)
- [x] 7.5 Add last-accessed info section showing most recent access log entry
- [x] 7.6 Add recent access history section (last 3 entries) in reveal dialog
- [x] 7.7 Implement `action_copy_credential()` method that logs "copy" action and returns decrypted value

## 8. SCSS & JavaScript

- [x] 8.1 Add environment color variables: production (#22c55e), staging (#eab308), development (#3b82f6), testing (#9ca3af)
- [x] 8.2 Add credential status badge styles: healthy, warning, expired, stale
- [x] 8.3 Add dashboard widget card styles: summary cards, list widgets, chart container
- [x] 8.4 Add credential card styles for the subscription form tab
- [x] 8.5 Add wizard step indicator styles
- [x] 8.6 Implement auto-close timer JavaScript for reveal dialog
- [x] 8.7 Implement copy-to-clipboard JavaScript with visual feedback
- [x] 8.8 Implement key type auto-detection JavaScript (live as user types in wizard)

## 9. Testing & Validation

- [ ] 9.1 Test migration from current module version: verify environment default, constraint update, no data loss
- [ ] 9.2 Test credential versioning: create, update, verify versions accumulate, verify copy doesn't copy secrets
- [ ] 9.3 Test access logging: reveal creates log entry, reveal blocked if log fails, copy creates log entry
- [ ] 9.4 Test RBAC: devops can't see costs, manager can't reveal, admin sees everything
- [ ] 9.5 Test dashboard: all widgets render, widget visibility correct per group
- [ ] 9.6 Test credential wizard: all 3 steps work, auto-detection triggers, password generator works
- [ ] 9.7 Test reveal dialog: auto-close timer (default + custom), copy button, audit warning displayed
- [ ] 9.8 Test historical version reveal: decryptable for devops/admin, hidden for managers, audit-logged
- [ ] 9.9 Test cron jobs: renewal date updates, expiry warnings, rotation warnings, access log cleanup
- [ ] 9.10 Test access log cleanup: entries older than retention period deleted, custom retention honored
- [ ] 9.11 Test kanban states: subscription kanban reflects credential expiry and rotation health
- [ ] 9.12 Test module upgrade path with real or simulated production data
