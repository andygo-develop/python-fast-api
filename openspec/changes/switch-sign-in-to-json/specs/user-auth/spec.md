## ADDED Requirements

### Requirement: Rejection of non-JSON request bodies

The sign-in endpoint SHALL accept a JSON request body and SHALL reject a body in any other encoding,
including form encoding, with `422 Unprocessable Content`. Its published schema SHALL declare
`application/json` as the only accepted content type.

#### Scenario: A form-encoded body is rejected

- **WHEN** a request is sent to `POST /auth/sign-in` with correct credentials encoded as `application/x-www-form-urlencoded`
- **THEN** the system responds `422 Unprocessable Content`
- **AND** no access token is issued, even though the credentials themselves were correct

#### Scenario: A malformed or absent body is rejected

- **WHEN** a request is sent to `POST /auth/sign-in` with no body, or with a body that is not valid JSON
- **THEN** the system responds `422 Unprocessable Content`
- **AND** no access token is issued

#### Scenario: Only JSON is published as an accepted content type

- **WHEN** the OpenAPI schema is retrieved
- **THEN** the request body for `POST /auth/sign-in` declares `application/json` and no other content type

## MODIFIED Requirements

### Requirement: Credential exchange for an access token

The system SHALL expose an authentication endpoint at `POST /auth/sign-in` that accepts a username and
password as properties of a JSON request body, and SHALL respond with a signed, time-limited access
token when the credentials match a stored user.

The response body SHALL contain the token and the token type `bearer`. The token SHALL identify the
authenticated user and SHALL carry an expiry timestamp.

#### Scenario: Valid credentials are exchanged for a token

- **WHEN** a request is sent to `POST /auth/sign-in` with the username and correct password of an existing user
- **THEN** the system responds `200 OK` with a body containing a non-empty access token and the token type `bearer`
- **AND** the returned token is accepted by endpoints requiring authentication until it expires

#### Scenario: Credentials are never echoed back

- **WHEN** any request is made to `POST /auth/sign-in`, successful or not
- **THEN** the response body and response headers contain neither the submitted password nor any stored password material

### Requirement: Rejection of unrecognized sign-in fields

The sign-in endpoint SHALL accept exactly two properties, `username` and `password`, and SHALL reject
any request carrying a property it does not recognize with `422 Unprocessable Content`, naming the
offending property.

The endpoint SHALL NOT document or accept OAuth2 password-flow parameters it does not use —
`grant_type`, `scope`, `client_id` and `client_secret` — and its published schema SHALL list only the
two credential properties.

#### Scenario: An unrecognized field is rejected

- **WHEN** a request is sent to `POST /auth/sign-in` with valid `username` and `password` plus any additional property
- **THEN** the system responds `422 Unprocessable Content`
- **AND** the response body identifies the unrecognized property by name
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
