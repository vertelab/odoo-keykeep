# Credential Audit

## Purpose

Defines the audit logging system for credential access in Keykeep: reveal logging, access log visibility, audit reports, reveal dialog warnings, auto-close behavior, and log cleanup.

## Requirements

### Requirement: Reveal access logging

The system SHALL log every reveal of a credential's secret value. The log entry MUST be created before the value is displayed to the user. If logging fails, the reveal SHALL be blocked.

#### Scenario: Reveal creates audit entry

- **WHEN** a user with appropriate permissions clicks "Reveal" on a credential
- **THEN** an access log entry SHALL be created with the user's identity, credential identity, timestamp, action type "reveal", fields accessed, and IP address

#### Scenario: Reveal blocked on log failure

- **WHEN** the system fails to create an access log entry (e.g., database constraint violation)
- **THEN** the reveal operation SHALL be aborted and the credential value SHALL NOT be displayed

#### Scenario: Audit log captures fields accessed

- **WHEN** a user reveals a credential of type "API Key" which only has `key_value`
- **THEN** the access log SHALL record `fields_accessed = 'key_value'`

#### Scenario: Audit log for login credentials

- **WHEN** a user reveals a credential of type "Login" which has both `password` and `key_value`
- **THEN** the access log SHALL record `fields_accessed = 'both'`

### Requirement: Audit log visibility

The system SHALL display the access log for each credential to users with appropriate permissions, showing all reveal and rotation events.

#### Scenario: Access log displayed on credential form

- **WHEN** a user with `group_devops` or `group_admin` permissions views a credential
- **THEN** the access log SHALL be displayed showing timestamp, user, action type, fields accessed, and IP address for each entry

#### Scenario: Access log not visible to managers

- **WHEN** a user with only `group_manager` permissions (not devops or admin) views a credential
- **THEN** the access log SHALL NOT be visible

#### Scenario: Access log sorted by timestamp

- **WHEN** the access log is displayed
- **THEN** entries SHALL be sorted in reverse chronological order (most recent first)

### Requirement: Audit report view

The system SHALL provide a searchable, filterable view of all access log entries across all credentials.

#### Scenario: Filter audit log by user

- **WHEN** an admin views the audit report and filters by a specific user
- **THEN** only access log entries for that user SHALL be displayed

#### Scenario: Filter audit log by date range

- **WHEN** an admin views the audit report and sets a date range filter
- **THEN** only access log entries within that date range SHALL be displayed

#### Scenario: Filter audit log by subscription

- **WHEN** an admin views the audit report and filters by a subscription
- **THEN** only access log entries for credentials belonging to that subscription SHALL be displayed

### Requirement: Reveal dialog audit warning

The system SHALL display a warning in the reveal dialog informing the user that their access is being logged, showing what information is recorded.

#### Scenario: Audit warning displayed before reveal

- **WHEN** a user opens the reveal dialog
- **THEN** a warning message SHALL be displayed stating that the access will be logged, including the user's identity, timestamp, and IP address that will be recorded

#### Scenario: Last access information shown

- **WHEN** the reveal dialog opens
- **THEN** the date and user of the most recent access (if any) SHALL be displayed

### Requirement: Auto-close reveal dialog

The system SHALL automatically close the reveal dialog after a configurable timeout period for security. The timeout SHALL be configurable via the system parameter `keykeep.reveal_timeout_seconds`.

#### Scenario: Default auto-close after 60 seconds

- **WHEN** the reveal dialog is opened and no custom timeout is configured
- **THEN** the dialog SHALL automatically close after 60 seconds

#### Scenario: Custom timeout configured

- **WHEN** the system parameter `keykeep.reveal_timeout_seconds` is set to 120
- **THEN** the reveal dialog SHALL automatically close after 120 seconds

#### Scenario: Timeout disabled

- **WHEN** the system parameter `keykeep.reveal_timeout_seconds` is set to 0
- **THEN** the reveal dialog SHALL NOT automatically close

#### Scenario: Manual close resets timer

- **WHEN** a user manually closes the reveal dialog
- **THEN** the credential value SHALL be cleared from the UI and the auto-close timer SHALL be cancelled

### Requirement: Access log auto-cleanup

The system SHALL periodically remove access log entries older than a configurable retention period. The default retention period SHALL be 730 days (2 years).

#### Scenario: Default retention period

- **WHEN** the daily cleanup cron executes
- **THEN** all access log entries with `accessed_at` older than 730 days SHALL be deleted

#### Scenario: Custom retention period

- **WHEN** the system parameter `keykeep.access_log_retention_days` is set to 365
- **THEN** the cleanup cron SHALL delete entries older than 365 days

#### Scenario: Retention disabled

- **WHEN** the system parameter `keykeep.access_log_retention_days` is set to 0
- **THEN** no access log entries SHALL be deleted

### Requirement: Historical version access logging

The system SHALL log access to historical credential versions with a distinct action type.

#### Scenario: Reveal historical version creates audit entry

- **WHEN** a user reveals a historical credential version value
- **THEN** an access log entry SHALL be created with `action = 'reveal_version'`

#### Scenario: Historical version reveals appear in audit report

- **WHEN** an admin views the audit report
- **THEN** entries with `action = 'reveal_version'` SHALL be distinguishable from current-value reveals (`action = 'reveal'`)
