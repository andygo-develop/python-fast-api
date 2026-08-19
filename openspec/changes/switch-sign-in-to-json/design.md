## Context

See `proposal.md` — Why. The endpoint's form encoding is a fossil of
`OAuth2PasswordRequestForm`, which was removed when sign-in narrowed to exactly two fields. What
remains is a `SignInForm` Pydantic model declared with `Form()`; the model itself has nothing
form-specific about it.

That matters for how small this change is. The validation contract — `extra="forbid"`,
`min_length=1` on both fields — is expressed entirely in the Pydantic model and is independent of how
the body arrives. Switching the transport does not require rewriting any of it.

## Goals / Non-Goals

**Goals:**

- One request encoding across the whole API.
- Identical observable behaviour on every path except the encoding: same statuses, same bodies, same
  headers, same indistinguishable 401.
- A test suite that proves the *behaviour* survived the transport change, not merely that the happy
  path still works.

**Non-Goals:**

- Content negotiation or a deprecation window that accepts both encodings. Explicitly declined.
- Any change to responses, to token issuance, or to how protected endpoints authenticate.
- Removing `python-multipart`. It arrives with `fastapi[standard]` and is not ours to drop.

## Decisions

### 1. A plain body model, not `Body()` with an explicit media type

Removing the `Form()` marker is the entire change at the routing layer:

```python
def sign_in(credentials: SignInRequest, auth_service: ...) -> Token:
```

A Pydantic model parameter with no marker is already a JSON body in FastAPI, and it publishes
`application/json` as the only accepted content type. Adding `Body(media_type=...)` would restate the
default and give a second place for the contract to drift.

*Alternative considered:* keeping `Form()` and adding a parallel JSON route. Rejected with the
"accept both" option — two paths through the same validation is where error behaviour silently
diverges.

### 2. `SignInForm` becomes `SignInRequest`

The class is no longer a form, and a name that says otherwise is the kind of small lie that outlives
the person who understands it. Renaming is free here: the symbol is referenced in exactly two places.

Its body is unchanged — same two fields, same `min_length=1`, same `extra="forbid"` — because the
strictness was never a property of form encoding.

### 3. Error behaviour is inherited, not re-implemented

The 422 shapes were verified against this project's FastAPI before planning:

| Request | Result |
|---|---|
| Valid JSON | `200` |
| Unknown property | `422 extra_forbidden`, naming the property |
| Empty `username` or `password` | `422 string_too_short` |
| Missing property | `422 missing` |
| Form-encoded body | `422 model_attributes_type` |
| Absent body | `422 missing` |

Every one of those is Pydantic's or FastAPI's own, so this change writes no error-handling code. The
form-encoded case is worth noting: it returns 422 rather than the `415 Unsupported Media Type` an
integrator might expect, because FastAPI treats the body as unparseable input rather than rejecting
the content type outright. That is FastAPI's behaviour, not a decision made here, and the spec
records the status the endpoint actually returns.

### 4. Tests change encoding, not assertions

Each affected test moves `data=` to `json=` and nothing else. If an assertion needs adjusting to keep
a test passing, that is a behaviour change and a signal to stop rather than to edit the assertion —
the whole claim of this change is that only the encoding differs.

One assertion deserves re-checking rather than trusting: the *credentials are never echoed back* test
scans the response for the submitted password. FastAPI's 422 body includes an `input` field echoing
the offending value, so a validation error on a password field could in principle surface it. That is
true of the current form-encoded endpoint too, but the JSON error shape is different enough to be
worth re-verifying rather than assuming it carries over.

## Risks / Trade-offs

- **A silent client break** → Any caller still posting a form gets a 422 that reads like a validation
  problem rather than "you used the wrong encoding". Nothing outside this repository is known to call
  the endpoint, so the blast radius is believed to be zero; the mitigation is that the README changes
  in the same change rather than later.
- **422 where 415 might be expected** → An integrator debugging a content-type mistake gets an error
  about the body's shape. Accepted: it is FastAPI's behaviour, and overriding it would mean writing
  exception-handling code this change otherwise does not need.
- **The password could appear in a 422 body** → Pre-existing rather than introduced, but the encoding
  change alters the error shape, so the existing test must be re-run and its coverage confirmed rather
  than assumed. If it does surface, that is a finding to report, not something to quietly patch here.
- **`python-multipart` stays as an unused dependency** → Harmless and not removable independently of
  `fastapi[standard]`. Worth knowing so nobody later concludes form support is still intended.
