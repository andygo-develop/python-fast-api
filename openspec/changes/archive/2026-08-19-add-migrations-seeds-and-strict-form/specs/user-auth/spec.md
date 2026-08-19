## ADDED Requirements

### Requirement: Rejection of unrecognized sign-in fields

The sign-in endpoint SHALL accept exactly two form fields, `username` and `password`, and SHALL reject
any request carrying a field it does not recognize with `422 Unprocessable Content`, naming the
offending field.

The endpoint SHALL NOT document or accept OAuth2 password-flow parameters it does not use —
`grant_type`, `scope`, `client_id` and `client_secret` — and its published schema SHALL list only the
two credential fields.

#### Scenario: An unrecognized field is rejected

- **WHEN** a request is sent to `POST /auth/sign-in` with valid `username` and `password` plus any additional form field
- **THEN** the system responds `422 Unprocessable Content`
- **AND** the response body identifies the unrecognized field by name
- **AND** no access token is issued, even though the credentials themselves were correct

#### Scenario: Previously tolerated OAuth2 parameters are rejected

- **WHEN** a request is sent to `POST /auth/sign-in` with valid credentials and any of `grant_type`, `scope`, `client_id` or `client_secret`
- **THEN** the system responds `422 Unprocessable Content`
- **AND** no access token is issued

#### Scenario: Only the two credential fields are published

- **WHEN** the OpenAPI schema is retrieved
- **THEN** the request body schema for `POST /auth/sign-in` declares `username` and `password` and no other property

#### Scenario: Exactly the two credential fields still succeed

- **WHEN** a request is sent to `POST /auth/sign-in` with only `username` and `password`, both valid
- **THEN** the system responds `200 OK` with an access token, unchanged from previous behaviour
