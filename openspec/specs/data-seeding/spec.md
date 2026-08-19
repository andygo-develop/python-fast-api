# data-seeding Specification

## Purpose

Defines how a development or test database is populated with a known starting dataset, so that every
developer works against the same accounts and a scenario can rely on a user existing without creating
one by hand.

## Requirements

### Requirement: Seeding creates a known dataset

The system SHALL provide a command that populates the database with a documented set of user accounts
whose credentials are known, so they can be used to sign in immediately after seeding.

#### Scenario: Seeding an empty database

- **WHEN** the seed command is run against an empty, migrated database
- **THEN** the documented seed users exist
- **AND** each seeded user can sign in with the documented password and receive an access token
- **AND** the command reports which users it created

### Requirement: Seeding is idempotent

Running the seed command more than once SHALL leave the database in the same state as running it once.
It SHALL NOT duplicate records, overwrite changes made since the last run, or fail on the second run.

#### Scenario: Seeding twice

- **WHEN** the seed command is run against a database that has already been seeded
- **THEN** the command succeeds and reports that there was nothing to create
- **AND** the number of user records is unchanged

### Requirement: Seeding is refused outside development environments

The seed command SHALL refuse to run when `ENVIRONMENT` is `staging` or `production`, so that accounts
with published passwords cannot be created in a deployed environment.

#### Scenario: Seeding is blocked in a deployed environment

- **WHEN** the seed command is run with `ENVIRONMENT` set to `staging` or `production`
- **THEN** the command exits with an error naming the environment as the reason
- **AND** no records are created

#### Scenario: Seeding is permitted in development

- **WHEN** the seed command is run with `ENVIRONMENT` set to `local` or `test`
- **THEN** seeding proceeds
