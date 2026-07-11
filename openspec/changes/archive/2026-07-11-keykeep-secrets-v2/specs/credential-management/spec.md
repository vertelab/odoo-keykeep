## ADDED Requirements

### Requirement: Multi-step credential creation wizard

The system SHALL provide a wizard for creating new credentials that guides the user through distinct steps: identification, secret value entry, and optional details.

#### Scenario: Wizard step 1 — identification

- **WHEN** a user opens the credential creation wizard
- **THEN** the first step SHALL prompt for label (name), credential type, and environment, with the subscription pre-filled from context

#### Scenario: Wizard step 2 — secret value

- **WHEN** a user proceeds from step 1 to step 2
- **THEN** the wizard SHALL display input fields appropriate for the selected credential type:
  - API Key / Token: a textarea for the key value with auto-trimming
  - Login: username and password fields with a password visibility toggle
  - Certificate / Other: a textarea
- **AND** the wizard SHALL display a warning that the value will be encrypted and access will be logged

#### Scenario: Wizard step 3 — optional details

- **WHEN** a user proceeds from step 2 to step 3
- **THEN** the wizard SHALL display optional fields: purpose, expiry date, renewal reminder checkbox, and notes

#### Scenario: Wizard saves credential

- **WHEN** a user completes all required steps and clicks "Save"
- **THEN** a new `keykeep.credential` SHALL be created with the provided values, the secret SHALL be encrypted, and a version 1 record SHALL be created

#### Scenario: Wizard cancel discards data

- **WHEN** a user clicks "Cancel" at any step
- **THEN** all entered data SHALL be discarded and no credential SHALL be created

### Requirement: Key type auto-detection

The system SHALL attempt to detect the type of API key being entered and display a visual indicator.

#### Scenario: Stripe key detected

- **WHEN** a user pastes a value starting with `sk_live_` or `sk_test_` into the key value field
- **THEN** the wizard SHALL display an indicator "Stripe Secret Key detected"

#### Scenario: GitHub token detected

- **WHEN** a user pastes a value starting with `ghp_` into the key value field
- **THEN** the wizard SHALL display an indicator "GitHub Personal Access Token detected"

#### Scenario: No pattern matched

- **WHEN** a user pastes a key that does not match any known pattern
- **THEN** no detection indicator SHALL be displayed

### Requirement: Password generator in credential wizard

The system SHALL offer a password generator for login-type credentials.

#### Scenario: Generate strong password

- **WHEN** a user clicks "Generate" next to the password field for a login-type credential
- **THEN** a cryptographically strong password (minimum 16 characters, mixed case, digits, symbols) SHALL be generated and displayed in the field

#### Scenario: Generated password is encrypted

- **WHEN** the credential is saved with a generated password
- **THEN** the password SHALL be encrypted using the same encryption strategy as manually entered passwords

### Requirement: Redesigned reveal dialog

The system SHALL display a redesigned reveal dialog with audit warning, credential context, value display with copy button, and auto-close countdown.

#### Scenario: Reveal dialog shows credential context

- **WHEN** a user opens the reveal dialog
- **THEN** the dialog SHALL display the credential name, subscription name, environment, and credential type

#### Scenario: Reveal dialog shows secret value with copy button

- **WHEN** the reveal dialog displays the decrypted value
- **THEN** a copy-to-clipboard button SHALL be displayed adjacent to the value

#### Scenario: Reveal dialog shows recent access history

- **WHEN** the reveal dialog opens
- **THEN** the last 3 access log entries for this credential SHALL be displayed (if any exist)

### Requirement: Standalone credential management view

The system SHALL provide a dedicated top-level view for managing all credentials, independent of the subscription form.

#### Scenario: Credentials menu item

- **WHEN** a user with `group_devops` or `group_admin` permissions navigates the Keykeep menu
- **THEN** a "Credentials" menu item SHALL be visible between "Dashboard" and "Subscriptions"

#### Scenario: Credential list view

- **WHEN** a user opens the Credentials view
- **THEN** a list SHALL display all credentials with columns: name, subscription, environment, type, status (OK/Warning/Expired), expiry date, and last accessed date

#### Scenario: Filter by environment

- **WHEN** a user applies an environment filter on the credential list
- **THEN** only credentials matching the selected environment SHALL be displayed

#### Scenario: Filter by status

- **WHEN** a user applies a status filter (e.g., "Expiring Soon")
- **THEN** only credentials matching that status SHALL be displayed

#### Scenario: Credential kanban grouped by environment

- **WHEN** a user switches to kanban view in the Credentials section
- **THEN** credentials SHALL be grouped by environment column (Production, Staging, Development, Testing)

### Requirement: Redesigned credentials tab in subscription form

The subscription form's credentials tab SHALL be redesigned to display credentials as cards grouped by environment, with health indicators.

#### Scenario: Credentials grouped by environment in form

- **WHEN** a user views the credentials tab on a subscription form
- **THEN** credentials SHALL be displayed in cards grouped under environment headers (Production, Staging, Development, Testing)

#### Scenario: Credential card shows summary

- **WHEN** a credential card is displayed
- **THEN** it SHALL show: credential name, type icon, masked value (last 4 characters), status indicator, and action buttons (Reveal, Copy, Edit)

#### Scenario: Environment sections with credential count

- **WHEN** an environment section is displayed
- **THEN** it SHALL show the count of credentials in that environment and a summary indicator (green if all OK, yellow if any warning, red if any expired)

#### Scenario: Rotation health warning in tab

- **WHEN** the credentials tab is viewed and one or more credentials have not been modified for more than 90 days
- **THEN** a warning banner SHALL be displayed at the top of the tab listing the stale credentials

### Requirement: Copy credential value to clipboard

The system SHALL provide a one-click copy action for credential values from the credential card or reveal dialog.

#### Scenario: Copy button on credential card

- **WHEN** a user clicks the copy button on a credential card (without opening reveal dialog)
- **THEN** the credential value SHALL be decrypted, copied to the system clipboard, and an access log entry with action "copy" SHALL be created

#### Scenario: Copy confirmation

- **WHEN** a value is successfully copied to clipboard
- **THEN** a temporary visual confirmation SHALL be displayed (e.g., button text changes to "Copied!" for 2 seconds)
