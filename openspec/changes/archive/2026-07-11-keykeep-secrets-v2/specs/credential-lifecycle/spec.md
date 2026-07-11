## ADDED Requirements

### Requirement: Credential environments

The system SHALL support environments for credentials with the values `production`, `staging`, `development`, and `testing`. Each credential MUST have exactly one environment.

#### Scenario: Create credential with environment

- **WHEN** a user creates a new credential and selects environment "staging"
- **THEN** the credential is stored with `environment = 'staging'`

#### Scenario: Default environment for existing credentials

- **WHEN** the module is upgraded from a version without environment support
- **THEN** all existing credentials SHALL have `environment` set to `'production'`

#### Scenario: Unique constraint includes environment

- **WHEN** a user attempts to create a credential with the same `(name, subscription_id, environment)` as an existing credential
- **THEN** the system SHALL reject the creation with a validation error

#### Scenario: Same name allowed across environments

- **WHEN** a user creates two credentials with the same name and subscription but different environments (e.g., "API Key" in production and "API Key" in staging)
- **THEN** both credentials SHALL be created successfully

#### Scenario: Filter credentials by environment

- **WHEN** a user views the credential list and filters by environment "staging"
- **THEN** only credentials with `environment = 'staging'` SHALL be displayed

### Requirement: Credential version history

The system SHALL preserve a complete history of credential value changes. Each time a credential's `username`, `password`, or `key_value` is modified, a new version record SHALL be created.

#### Scenario: Version created on create

- **WHEN** a new credential is created with a password or key value
- **THEN** a version 1 record SHALL be created containing the encrypted snapshot of the credential value, the creating user, and a timestamp

#### Scenario: Version created on update

- **WHEN** an existing credential's password is changed
- **THEN** a new version record SHALL be created with an incremented version number, the new encrypted value, the editing user, and a timestamp

#### Scenario: Version history is viewable

- **WHEN** a user with appropriate permissions views a credential
- **THEN** the system SHALL display the version history showing version number, timestamp, user who made the change, and change note (if provided)

#### Scenario: Copy does not copy secret values

- **WHEN** a user duplicates a credential using Odoo's copy action
- **THEN** the copy SHALL have empty password and key_value fields, requiring new values to be entered

#### Scenario: Unlink cleans up versions

- **WHEN** a credential is deleted
- **THEN** all associated version records SHALL be deleted and all encrypted data in ir.config_parameter SHALL be removed

### Requirement: Credential rotation tracking

The system SHALL track when each credential was last updated (effectively "rotated") and SHALL surface credentials that have not been rotated for an extended period.

#### Scenario: Rotation age is computed

- **WHEN** a credential was last modified 120 days ago
- **THEN** the system SHALL display a warning indicating the credential has not been rotated for 120 days

#### Scenario: Stale rotation warning threshold

- **WHEN** a credential has not been modified for more than 90 days
- **THEN** the system SHALL flag it as "stale rotation" in the credential health view

#### Scenario: Rotation via value change

- **WHEN** a user updates any of `password`, `key_value`, or `username` on a credential
- **THEN** the system SHALL treat this as a rotation and update the last-modified timestamp

### Requirement: Credential expiry linked to subscription status

The system SHALL reflect credential expiry state in the subscription's kanban status.

#### Scenario: Expiring credential affects subscription kanban

- **WHEN** a subscription has at least one active credential expiring within the subscription's `notify_days_before` threshold
- **THEN** the subscription's `kanban_state` SHALL be `'warning'` (unless already `'critical'` due to renewal)

#### Scenario: Expired credential affects subscription kanban

- **WHEN** a subscription has at least one credential with `expiry_date` in the past
- **THEN** the subscription's `kanban_state` SHALL be `'critical'`

#### Scenario: All credentials healthy

- **WHEN** a subscription has no credentials expiring within the threshold and no expired credentials
- **THEN** the credential health SHALL NOT downgrade the subscription's `kanban_state` beyond what renewal tracking sets

### Requirement: Historical version value visibility

The system SHALL allow users with reveal permission to view decrypted values of previous credential versions. Each historical reveal SHALL be audit-logged.

#### Scenario: User reveals a previous version value

- **WHEN** a user with `group_devops` or `group_admin` permission clicks "Reveal" on a historical version in the version history list
- **THEN** the decrypted value SHALL be displayed and an access log entry with `action = 'reveal_version'` SHALL be created

#### Scenario: User without reveal permission views history

- **WHEN** a user with only `group_manager` permission views the version history
- **THEN** the version list SHALL display metadata (version number, timestamp, username, change note) but SHALL NOT show decrypted values or reveal buttons

#### Scenario: Deleted credential versions are not accessible

- **WHEN** a credential is deleted
- **THEN** all its version records and encrypted data SHALL be deleted and SHALL NOT be accessible
