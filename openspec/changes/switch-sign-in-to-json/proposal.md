## Why

`POST /auth/sign-in` is the only endpoint in the API that takes a request body, and it takes that body
as `application/x-www-form-urlencoded` while every response it produces is JSON. That asymmetry is a
leftover: the form encoding came from `OAuth2PasswordRequestForm`, which the endpoint no longer uses.
Nothing about the endpoint requires form encoding any more, and nothing else in the API speaks it.

The cost is paid by every client. A JSON API that has exactly one form-encoded endpoint is a special
case an integrator has to notice and handle — a different serializer, a different `Content-Type`, and
a shape that no other call in the API uses.

## What Changes

- **BREAKING**: `POST /auth/sign-in` accepts `application/json` and no longer accepts form encoding.
  A form-encoded request receives `422 Unprocessable Content`.

  ```json
  { "username": "alice", "password": "..." }
  ```

- Field-level strictness is preserved exactly as it is today: unknown properties are rejected with
  `422 extra_forbidden`, and empty `username` or `password` is rejected as invalid input rather than
  treated as a failed sign-in.
- Every authentication outcome keeps its current status and body: `200` with the token, and a single
  generic `401` for wrong password, unknown user, and inactive account alike.
- `SignInForm` is renamed to `SignInRequest` — it is no longer a form.
- `README.md` sign-in examples move from `curl -d "username=..."` to a JSON body.

Nothing else in the API changes. `GET /users/me` has no request body, and bearer-token authentication,
token issuance, and the response schema are all untouched.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `user-auth`: two requirements describe the request as form-encoded and must change. *Credential
  exchange for an access token* currently specifies credentials "submitted as form-encoded fields";
  *Rejection of unrecognized sign-in fields* currently specifies "exactly two form fields". Both keep
  their existing behaviour and scenarios — only the encoding they name changes — and a new requirement
  covers rejection of non-JSON request bodies.

## Impact

**Dependencies**: none added. `python-multipart` stays in the tree because `fastapi[standard]` depends
on it; it simply stops being used by this endpoint.

**Changed code**:
- `app/auth/schemas.py` — `SignInForm` becomes `SignInRequest`, unchanged in its fields and its
  `extra="forbid"` configuration.
- `app/auth/router.py` — the parameter loses its `Form()` marker and becomes a plain body model. The
  handler body does not change.

**Changed tests**: the four existing sign-in test modules post with `data=`; they move to `json=`. The
assertions themselves — status codes, identical 401 bodies, `WWW-Authenticate` headers, the
password-never-echoed check — are unaffected.

**Changed docs**: `README.md` sign-in examples and the note describing form-encoded input.

**Client impact**: any caller posting a form must switch to JSON. Within this repository that is the
README examples and the test suite; no other consumer is known.

**Out of scope**: content negotiation or accepting both encodings, changing any response body, and
altering the bearer-token scheme used by protected endpoints.
