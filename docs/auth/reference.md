# Authentication reference

## At a glance

#### `Auth`

| Member | Notes |
|---|---|
| `Auth.auth()` | The shared instance |
| `current_user` | A `User`, or `None` |
| `add_state_did_change_listener(listener)` / `add_id_token_did_change_listener(listener)` | `listener(user)`; returns an `AuthStateListener` (`.remove()`) |
| `sign_in_with_email_password(email, password, cb)` / `create_user_with_email_password(...)` | `cb(AuthDataResult, error)` |
| `sign_in_anonymously(cb)`, `sign_in_with_custom_token(token, cb)` | |
| `sign_in_with_credential(credential, cb)`, `sign_in_with_provider(OAuthProvider, cb)` | |
| `send_sign_in_link(email, settings, cb)`, `is_sign_in_with_email_link(link)`, `sign_in_with_email_link(email, link, cb)` | Passwordless |
| `send_password_reset(email, cb, settings)`, `verify_password_reset_code(code, cb)`, `confirm_password_reset(code, password, cb)` | |
| `check_action_code(code, cb)`, `apply_action_code(code, cb)` | `cb(ActionCodeInfo, error)` / `cb(error)` |
| `sign_out()`, `update_current_user(user, cb)`, `revoke_token(code, cb)` | |
| `get_stored_user(access_group)` | `(user, error)`: the user in a shared keychain |
| `use_emulator(host, port)`, `is_using_emulator`, `language_code`, `use_app_language()`, `tenant_id`, `app_verification_disabled_for_testing`, `use_user_access_group(group)` | Settings |
| `can_handle_url(url)`, `can_handle_notification(user_info)`, `set_apns_token(token, type)` | App delegate hooks (phone, OAuth) |

#### `User`

- Profile: `uid`, `email`, `display_name`, `phone_number`, `photo_url`, `provider_id`,
  `is_anonymous`, `is_email_verified`, `provider_data` (list of `UserInfo`),
  `metadata` (`UserMetadata`: `creation_date`, `last_sign_in_date`), `tenant_id`,
  `refresh_token`, `is_signed_in`
- Tokens: `get_id_token(cb, force_refresh=False)`, `get_id_token_result(cb, force_refresh=False)` → `IDTokenResult` (`token`, `claims`, `expiration_date`, `issued_at_date`, `auth_date`, `sign_in_provider`, `sign_in_second_factor`)
- Account: `reload`, `delete`, `update_password`, `update_email`, `update_profile(cb, *, display_name, photo_url)`, `update_phone_number`, `send_email_verification`, `send_email_verification_before_updating_email`
- Providers: `link_with_credential`, `link_with_provider`, `unlink`, `reauthenticate_with_credential`, `reauthenticate_with_provider`

#### Credentials and providers

| Provider | Make a credential |
|---|---|
| `EmailAuthProvider` | `credential(email, password)`, `credential_with_link(email, link)` |
| `GoogleAuthProvider` | `credential(id_token, access_token)` (or `auth.google`) |
| `OAuthProvider` | `OAuthProvider(id, scopes, custom_parameters)` for web flows; `credential(id, id_token, access_token, raw_nonce)`; `apple_credential(id_token, raw_nonce, given_name, family_name)` (or `auth.apple`) |
| `PhoneAuthProvider` | `verify_phone_number(number, cb)`, then `credential(verification_id, code)` |
| `FacebookAuthProvider` | `credential(access_token)` |
| `GitHubAuthProvider` | `credential(token)` |
| `TwitterAuthProvider` | `credential(token, secret)` |
| `GameCenterAuthProvider` | `get_credential(cb)` |

Each has a `PROVIDER_ID`. `AuthDataResult` has `user`, `additional_user_info`
(`provider_id`, `is_new_user`, `username`, `profile`) and `credential`.

#### Multi-factor

- `User.multi_factor` → `MultiFactor`: `enrolled_factors`, `get_session(cb)`, `enroll(assertion, display_name, cb)`, `unenroll(factor_or_uid, cb)`
- `MultiFactorInfo` (`uid`, `factor_id`, `display_name`, `enrollment_date`), `PhoneMultiFactorInfo` (+ `phone_number`)
- `PhoneMultiFactorGenerator.assertion(credential)`; `PhoneAuthProvider.verify_phone_number(..., multi_factor_session=)`, `verify_phone_number_for_sign_in(hint, session, cb)`
- `TOTPMultiFactorGenerator.generate_secret(session, cb)`, `assertion_for_enrollment(secret, code)`, `assertion_for_sign_in(enrollment_id, code)`; `TOTPSecret.shared_secret_key()`, `generate_qr_code_url(account, issuer)`, `open_in_otp_app(url)`
- `MultiFactorResolver` (from `AuthError.resolver`): `hints`, `session`, `resolve_sign_in(assertion, cb)`

#### Facebook (`pyios_firebase.auth.facebook`)

`initialize_facebook()`, `start_facebook_sign_in(cb, permissions, limited)`, `get_facebook_credential(cb, permissions, limited)`, `sign_out_of_facebook()`, `on_facebook_handle_url(url)`, `on_facebook_handle_url_kivy(...)`

#### Errors

`AuthError` (keys above, plus `resolver` for `SECOND_FACTOR_REQUIRED`) and `AuthErrorCode`: every `FIRAuthErrorCode` of the SDK,
by name (`EMAIL_ALREADY_IN_USE`, `WRONG_PASSWORD`, `REQUIRES_RECENT_LOGIN`,
`ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`, ...).

## `pyios_firebase.auth`

::: pyios_firebase.auth

## `pyios_firebase.auth.google`

::: pyios_firebase.auth.google

## `pyios_firebase.auth.apple`

::: pyios_firebase.auth.apple

## `pyios_firebase.auth.facebook`

::: pyios_firebase.auth.facebook

## `pyios_firebase.auth.multi_factor`

::: pyios_firebase.auth.multi_factor
