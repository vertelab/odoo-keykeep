# Keykeep Dashboard

## Purpose

Defines the Keykeep dashboard — the main landing page with adaptive widgets for different user personas (economy, devops, admin).

## Requirements

### Requirement: Dashboard as main landing page

The system SHALL provide a dashboard page as the primary Keykeep landing page, accessible from the top-level menu. The dashboard SHALL be the default view when navigating to Keykeep.

#### Scenario: Dashboard is first menu item

- **WHEN** a user opens the Keykeep menu
- **THEN** "Dashboard" SHALL be the first item, above "Subscriptions"

#### Scenario: Dashboard loads without errors

- **WHEN** a user navigates to the Dashboard
- **THEN** all widgets SHALL render and display data without JavaScript or server errors

### Requirement: Cost summary widget

The system SHALL display a cost summary widget showing total monthly cost of active subscriptions.

#### Scenario: Cost widget for managers

- **WHEN** a user with `group_manager` or `group_admin` permissions views the dashboard
- **THEN** the cost summary widget SHALL display the sum of `cost_amount` for all active subscriptions

#### Scenario: Cost widget hidden for devops

- **WHEN** a user with only `group_devops` permissions views the dashboard
- **THEN** the cost summary widget SHALL NOT be displayed

#### Scenario: Cost widget shows trend

- **WHEN** the cost summary widget is displayed
- **THEN** it SHALL show the percentage change compared to the previous month

### Requirement: Subscription health widget

The system SHALL display a widget showing subscription health metrics: active count, renewals within 30 days, and overdue renewals.

#### Scenario: Subscription health for all personas

- **WHEN** any user with Keykeep access views the dashboard
- **THEN** the subscription health widget SHALL display the count of active subscriptions and the count of subscriptions due for renewal within 30 days

#### Scenario: Overdue count

- **WHEN** the subscription health widget is displayed and there are subscriptions past their renewal date
- **THEN** the overdue count SHALL be displayed with a red indicator

### Requirement: Credential health widget

The system SHALL display a credential health widget showing credential status across all subscriptions.

#### Scenario: Credential health for devops and admins

- **WHEN** a user with `group_devops` or `group_admin` permissions views the dashboard
- **THEN** the credential health widget SHALL display counts of healthy, warning (expiring within 30 days), and expired credentials

#### Scenario: Credential health hidden for managers

- **WHEN** a user with only `group_manager` permissions views the dashboard
- **THEN** the credential health widget SHALL NOT be displayed

#### Scenario: Stale rotation count

- **WHEN** the credential health widget is displayed
- **THEN** it SHALL show the count of credentials that have not been modified for more than 90 days

### Requirement: Upcoming renewals widget

The system SHALL display a list of upcoming subscription renewals, ordered by nearest renewal date.

#### Scenario: Renewals for managers and admins

- **WHEN** a user with `group_manager` or `group_admin` permissions views the dashboard
- **THEN** the upcoming renewals widget SHALL display the next 5 active subscriptions ordered by `next_renewal_date` ascending

#### Scenario: Renewals hidden for devops

- **WHEN** a user with only `group_devops` permissions views the dashboard
- **THEN** the upcoming renewals widget SHALL NOT be displayed

#### Scenario: Renewal shows days remaining

- **WHEN** the upcoming renewals widget displays a subscription
- **THEN** it SHALL show the number of days until the renewal date with color coding (green >14d, yellow ≤14d, red overdue)

### Requirement: Recent activity widget

The system SHALL display recent credential access and rotation events for users with appropriate permissions.

#### Scenario: Activity for devops and admins

- **WHEN** a user with `group_devops` or `group_admin` permissions views the dashboard
- **THEN** the recent activity widget SHALL display the most recent 10 access log entries, each showing timestamp, user, action, and credential name

#### Scenario: Activity hidden for managers

- **WHEN** a user with only `group_manager` permissions views the dashboard
- **THEN** the recent activity widget SHALL NOT be displayed

### Requirement: Cost forecast chart widget

The system SHALL display a chart showing projected monthly costs for the next 6 months, grouped by category.

#### Scenario: Chart for managers and admins

- **WHEN** a user with `group_manager` or `group_admin` permissions views the dashboard
- **THEN** the cost forecast chart SHALL display monthly cost projections for the next 6 months

#### Scenario: Chart hidden for devops

- **WHEN** a user with only `group_devops` permissions views the dashboard
- **THEN** the cost forecast chart SHALL NOT be displayed

#### Scenario: Chart grouped by category

- **WHEN** the cost forecast chart is displayed and categories exist
- **THEN** the chart SHALL group costs by `keykeep.category` using distinct colors

### Requirement: Quick actions widget

The system SHALL display quick action buttons for common tasks, adapted to user permissions.

#### Scenario: Quick actions for all users

- **WHEN** any Keykeep user views the dashboard
- **THEN** the quick actions widget SHALL display at minimum a "New Subscription" button

#### Scenario: Quick actions for devops and admins

- **WHEN** a user with `group_devops` or `group_admin` permissions views the dashboard
- **THEN** the quick actions widget SHALL additionally display "New Credential" and "View All Credentials" buttons

#### Scenario: Quick actions for managers and admins

- **WHEN** a user with `group_manager` or `group_admin` permissions views the dashboard
- **THEN** the quick actions widget SHALL additionally display a "Create Journal Entry" button
