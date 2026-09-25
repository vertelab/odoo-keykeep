# access-rights Specification

## Purpose

Keykeep access-modell: meny-synlighet kräver medlemskap i lägsta gruppnivå
(Keykeep User), Odoo-administratörer är automatiskt Keykeep-admins, grupperna
visas under egen rubrik på Åtkomsträttigheter, och API-nycklar/credentials
för en partner är synliga för den som kan läsa partnern (team-rätt).

## ADDED Requirements

### Requirement: Menu visibility requires Keykeep User
The system SHALL hide the Keykeep menu from internal users who are not
members of at least the Keykeep User group, and SHALL keep the Configuration
submenu gated at Keykeep Manager.

#### Scenario: Keykeep menu hidden without group
- **GIVEN** an internal user without the Keykeep User group
- **WHEN** the user opens the app menu
- **THEN** the Keykeep menu is not visible
- **AND** when the user is assigned Keykeep User, the Keykeep menu becomes
  visible

#### Scenario: Configuration stays manager-gated
- **GIVEN** a Keykeep User who is not a Manager
- **WHEN** the user opens the Keykeep menu
- **THEN** the Configuration submenu is not visible

### Requirement: Administrator automation
The system SHALL make Odoo administrators (Settings group,
`base.group_system`) automatically members of the Keykeep Admin group.

#### Scenario: Settings user is Keykeep Admin
- **GIVEN** a user in the Settings group
- **WHEN** the modules are installed
- **THEN** the user has Keykeep Admin implied
- **AND** thereby sees the Keykeep menu and all Keykeep model rights

### Requirement: Access groups under own category
The system SHALL display the Keykeep access groups under the "Keykeep"
heading on the user's Access Rights tab.

#### Scenario: Keykeep heading on user form
- **GIVEN** the Keykeep groups (User, Manager, DevOps, Admin)
- **WHEN** a user opens Åtkomsträttigheter on a user form
- **THEN** the groups appear under the "Keykeep" heading

### Requirement: Partner-scoped credential visibility
The system SHALL allow any user who can read a `res.partner` to view that
partner's API keys and credentials via the partner smart buttons (team
right), without granting global read access to `keykeep.credential` and
without lowering the existing permission levels.

#### Scenario: Partner reader sees the partner's credentials
- **GIVEN** a user with read access to a specific `res.partner`
- **WHEN** the user opens that partner's form
- **THEN** the API-key/credential smart buttons are available
- **AND** the user can view that partner's API keys and credentials

#### Scenario: No global credential read for lowest group
- **GIVEN** a Keykeep User (lowest level)
- **WHEN** the user accesses credentials outside the partner context
- **THEN** the user does NOT get global read access to all credentials
- **AND** partner-scoped visibility still works through the smart buttons

#### Scenario: Existing permission levels unchanged
- **GIVEN** the existing Keykeep Manager/DevOps/Admin credential rights
- **WHEN** the partner-scoped visibility is implemented
- **THEN** those permission levels are unchanged
- **AND** existing record rules (e.g. company-based) continue to apply
