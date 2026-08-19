## 1. Request model

- [x] 1.1 `app/auth/schemas.py`: rename `SignInForm` to `SignInRequest`, leaving its fields, `min_length=1` constraints and `extra="forbid"` configuration exactly as they are
- [x] 1.2 Update the class docstring: it explains the strictness in terms of form fields and the Swagger Authorize button, both of which are now out of date
- [x] 1.3 Confirm no other module still imports `SignInForm`

## 2. Route

- [x] 2.1 `app/auth/router.py`: take the model as a plain body parameter, dropping the `Form()` marker and the `Annotated[...]` wrapper it required
- [x] 2.2 Remove the now-unused `Form` import
- [x] 2.3 Confirm the handler body is otherwise untouched — same service call, same generic 401, same `Token` response
- [x] 2.4 Confirm the published request body declares `application/json` as its only content type — spec: *Only JSON is published as an accepted content type*

## 3. Tests

- [x] 3.1 `tests/test_sign_in.py`: move every `data=` to `json=`, changing no assertion
- [x] 3.2 `tests/test_sign_in_strict.py`: same, including the parametrised OAuth2-parameter cases
- [x] 3.3 `tests/test_seeds.py`: the seeded-user sign-in check posts a form; move it to `json=`
- [x] 3.4 `tests/conftest.py`: the `signed_in_token` fixture posts a form; move it to `json=`
- [ ] 3.5 Re-run the *credentials are never echoed back* test against the JSON error shape and confirm the submitted password does not appear in a 422 body — design Decision 4; report it rather than patching it if it does
- [ ] 3.6 New test — a form-encoded body with correct credentials returns 422 and issues no token — spec: *A form-encoded body is rejected*
- [ ] 3.7 New test — an absent body and a malformed JSON body each return 422 — spec: *A malformed or absent body is rejected*
- [ ] 3.8 New test — the OpenAPI request body declares only `application/json` — spec: *Only JSON is published as an accepted content type*
- [ ] 3.9 Confirm the existing extra-property, blank-field and missing-field tests still return 422 unchanged — spec: *An unrecognized field is rejected*, *Previously tolerated OAuth2 parameters are rejected*, *Missing credential fields*
- [ ] 3.10 Confirm the wrong-password and unknown-username responses are still byte-identical to each other — spec: *Wrong password*, *Unknown username*

## 4. Documentation

- [x] 4.1 `README.md`: change the sign-in `curl` example to post JSON with an explicit `Content-Type: application/json`
- [x] 4.2 `README.md`: replace the note describing form-encoded input, and add form-encoded requests to the outcome table as a 422
- [x] 4.3 `README.md`: check the Quick start and Authorize instructions for any remaining form-encoded reference
- [x] 4.4 `CLAUDE.md`: update the sign-in convention note, which describes the accepted input as form fields

## 5. Verification

- [ ] 5.1 Run `uv run pytest` and confirm the whole suite passes, reporting real output
- [ ] 5.2 Against a running server: sign in with a JSON body, then call `GET /users/me` with the returned token
- [ ] 5.3 Against a running server: confirm the same credentials sent as a form return 422, and that `/docs` shows a JSON request body for the endpoint
- [ ] 5.4 Confirm `/docs` Authorize still works end to end — it takes a pasted bearer token and is unaffected by the request encoding
