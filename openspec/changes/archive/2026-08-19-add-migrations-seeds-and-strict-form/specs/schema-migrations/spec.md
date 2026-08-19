## Purpose

Defines how the database schema is versioned, applied and reverted, so that a schema change is an
explicit, reviewable, ordered step rather than a side effect of running the application.

## ADDED Requirements

### Requirement: Migrations are the only source of schema

The system SHALL define its database schema exclusively through ordered migration scripts. Starting
the application SHALL NOT create, alter or drop any table.

#### Scenario: Starting the application does not change the schema

- **WHEN** the application starts against an empty database
- **THEN** no tables are created
- **AND** requests that depend on a table fail rather than silently succeeding against a schema the application invented

#### Scenario: Applying migrations builds the schema

- **WHEN** migrations are applied to an empty database
- **THEN** the schema contains a `users` table with the columns the application expects
- **AND** the recorded migration version matches the latest migration

### Requirement: Migrations are reversible and ordered

Each migration SHALL declare both how to apply and how to revert it, and SHALL record its position in
a single ordered history.

#### Scenario: A migration can be reverted

- **WHEN** the most recent migration is reverted
- **THEN** the schema returns to its previous state
- **AND** the recorded version moves back to the preceding migration

#### Scenario: Applying migrations twice is safe

- **WHEN** migrations are applied to a database that is already at the latest version
- **THEN** no schema change occurs and the operation succeeds

### Requirement: Migration target follows configuration

Migrations SHALL run against the database named by the application's own configuration, so that the
schema they build and the schema the application uses can never diverge.

#### Scenario: Migrations honour the configured database

- **WHEN** `DATABASE_URL` names a database and migrations are applied
- **THEN** the migrations are applied to that database and not to any default or hardcoded location
