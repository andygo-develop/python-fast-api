# user-auth Specification

## Purpose

Lets a person prove who they are by exchanging a username and password for a time-limited access token,
and lets any later request identify its caller by presenting that token. This is the identity primitive
every access-controlled capability in the system builds on.

## Requirements

### Requirement: Credential exchange for an access token

The system SHALL expose an authentication endpoint at `POST /auth/sign-in` that accepts a username and
password submitted as form-encoded fields, and SHALL respond with a signed, time-limited access token
when the credentials match a stored user.

The response body SHALL contain the token and the token type `bearer`. The token SHALL identify the
authenticated user and SHALL carry an expiry timestamp.

#### Scenario: Valid credentials are exchanged for a token

- **WHEN** a request is sent to `POST /auth/sign-in` with the username and correct password of an existing user
- **THEN** the system responds `200 OK` with a body containing a non-empty access token and the token type `bearer`
- **AND** the returned token is accepted by endpoints requiring authentication until it expires

#### Scenario: Credentials are never echoed back

- **WHEN** any request is made to `POST /auth/sign-in`, successful or not
- **THEN** the response body and response headers contain neither the submitted password nor any stored password material

### Requirement: Rejection of invalid credentials

The system SHALL reject an authentication attempt whose username is unknown or whose password does not
match the stored credential, and SHALL NOT reveal which of the two was wrong.

#### Scenario: Wrong password

- **WHEN** a request is sent to `POST /auth/sign-in` with an existing username and an incorrect password
- **THEN** the system responds `401 Unauthorized` with a generic authentication-failure message
- **AND** no access token is issued

#### Scenario: Unknown username

- **WHEN** a request is sent to `POST /auth/sign-in` with a username that does not exist
- **THEN** the system responds `401 Unauthorized`
- **AND** the response is indistinguishable from the wrong-password response in status code and message body, so the endpoint cannot be used to enumerate registered users

#### Scenario: Missing credential fields

- **WHEN** a request is sent to `POST /auth/sign-in` without a username field, without a password field, or with an empty value for either
- **THEN** the system responds `422 Unprocessable Content` describing the missing or invalid fields
- **AND** no access token is issued

### Requirement: Authenticated identity retrieval

The system SHALL expose `GET /users/me`, which returns the profile of the user identified by the access
token presented in the `Authorization` header using the `Bearer` scheme.

The returned profile SHALL expose only fields explicitly designated as publicly readable — at minimum
the user's identifier, username and account-active state — and SHALL NOT expose stored password
material under any field name.

#### Scenario: Valid token resolves to its user

- **WHEN** a request is sent to `GET /users/me` with the header `Authorization: Bearer <token>`, where `<token>` was issued to that user and has not expired
- **THEN** the system responds `200 OK` with that user's profile
- **AND** the response body contains no password hash and no password field

### Requirement: Rejection of absent or unusable tokens

The system SHALL refuse any request to an authenticated endpoint that presents no token, a token it
cannot verify, or a token whose expiry has passed. Every such refusal SHALL respond `401 Unauthorized`
and SHALL include a `WWW-Authenticate: Bearer` header.

#### Scenario: No token supplied

- **WHEN** a request is sent to `GET /users/me` with no `Authorization` header
- **THEN** the system responds `401 Unauthorized` with a `WWW-Authenticate: Bearer` header

#### Scenario: Malformed or tampered token

- **WHEN** a request is sent to `GET /users/me` with an `Authorization: Bearer` token that is not a well-formed token, or whose payload has been altered after signing, or that was signed with a different key
- **THEN** the system responds `401 Unauthorized`
- **AND** the response does not disclose why verification failed beyond a generic message

#### Scenario: Expired token

- **WHEN** a request is sent to `GET /users/me` with a token whose expiry timestamp is in the past
- **THEN** the system responds `401 Unauthorized`
- **AND** the token is refused no matter how recently it expired

#### Scenario: Token for a user that no longer exists or is inactive

- **WHEN** a request is sent with a validly signed, unexpired token identifying a user that has since been deleted or marked inactive
- **THEN** the system responds `401 Unauthorized`
- **AND** access is refused on every subsequent request with that token

### Requirement: Password storage

The system SHALL store user passwords only as a one-way hash produced by a deliberately slow,
salted password-hashing function. Plaintext passwords, reversible encryption, and general-purpose
fast digests SHALL NOT be used.

Each stored hash SHALL be salted such that two users choosing the same password produce different
stored values.

#### Scenario: Stored credential is not reversible

- **WHEN** a user's stored record is inspected directly in the database
- **THEN** the password field holds a hash that identifies its algorithm and parameters, not the original password
- **AND** the original password cannot be recovered from the stored value

#### Scenario: Identical passwords hash differently

- **WHEN** two users are created with the same password
- **THEN** their stored password values differ

### Requirement: Signing key configuration

The system SHALL read its token-signing key and token lifetime from configuration rather than source
code, and SHALL refuse to start outside a local development environment when the signing key is
missing or left at a placeholder value.

#### Scenario: Missing signing key outside local development

- **WHEN** the application starts in a non-local environment with no signing key configured, or with a well-known placeholder value
- **THEN** startup fails with an error naming the missing or invalid configuration
- **AND** the application does not begin accepting requests

#### Scenario: Token lifetime is configurable

- **WHEN** the configured access-token lifetime is changed and the application is restarted
- **THEN** tokens issued afterwards expire according to the new lifetime

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
