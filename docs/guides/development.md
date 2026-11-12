# Development and testing

```bash
uv sync --group dev
uv run pytest      # tests
uv run mypy        # strict type check of the package and of tests/typing
uv run pyright     # the checker behind VS Code's Pylance
uv run ruff check
```

## Releasing

Releases go to PyPI from GitHub Actions (`.github/workflows/release.yml`), with
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/): no API token.

1. Set `__version__` in `src/pyios_firebase/__init__.py`, and merge to `main`.
2. Tag the merge and push the tag:

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

   Or on GitHub: **Releases > Draft a new release**, type `v0.2.0` in **Choose
   a tag** (*Create new tag on publish*), target `main`, and **Publish
   release**. Publishing creates the tag.

The tag runs the checks, builds the sdist and the wheel, checks that the tag
matches `__version__`, publishes to PyPI, and attaches the files to the
GitHub Release (it creates the release for a pushed tag). **Run workflow** on the Release workflow publishes to TestPyPI
instead, as a dry run.

## End-to-end tests on the iOS Simulator

```bash
e2e/run_ios_e2e.sh
```

This builds a small Kivy app (`e2e/ios/`) with the wheel from your checkout and
the real Firebase iOS SDK, runs it in the iOS Simulator against the local
Firestore, Auth, Functions, Storage and Realtime Database emulators, and exits
non-zero if any test fails. The app is launched twice: the first launch runs
the suites and then crashes on purpose, and the second checks that Crashlytics
recorded the crash.

- Firestore: every value type, writes and field values, merges, queries and
  cursors, OR/AND filters, collection groups, aggregates, listeners and their
  change types, batches, transactions, and read sources.
- Auth: email/password, errors and their codes, state and ID token listeners,
  anonymous upgrade, linking and unlinking a provider, custom tokens and claims,
  phone sign-in, profile and tokens, re-authentication, password change and
  account deletion, password reset, email verification, email link sign-in,
  SMS multi-factor enrollment and sign-in, passing state in email links, the
  shared keychain, OAuth providers, and the Facebook SDK bridge. The emails and
  SMS codes are read from the Auth emulator's REST API. TOTP is skipped: the Auth
  emulator supports only SMS second factors.
- Functions: JSON round trip, `HttpsError` codes and details, unexpected errors,
  unknown functions, timeouts, the Auth context, regions, calls by URL, App
  Check tokens (normal and limited-use), and non-JSON data. The functions are
  Python Cloud Functions (`firebase_functions`) in `e2e/functions/main.py`.
- Storage: references, upload with metadata, metadata update and delete, download
  URL, download to memory and to a file, file upload, listing and paging, upload
  progress, cancel, and errors.
- Remote Config (no emulator exists): plist defaults, values and their sources,
  merged defaults, settings, a fetch failing cleanly offline, custom signals and
  the update listener.
- App Check: a Python custom provider serving the whole app, tokens and
  limited-use tokens, the token listener, settings, and the debug token from
  `FIRAAppCheckDebugToken`.
- Realtime Database: value types, listeners for values and child events (with
  previous keys), sorting and filtering, multi-path updates, server timestamps
  and increments, transactions (committed, aborted, raising), priorities and the
  export format, security rules errors, Python errors instead of aborts,
  `.info/connected` and `on_disconnect`.
- Analytics (no emulator exists): events, e-commerce items, screen views, user
  properties, consent with the SDK's own constants, IDs, and name checks.
- Crashlytics: logs, keys, non-fatal Python exceptions with their frames, the
  excepthook, and a real crash found again on the next launch, with its unsent
  report.
- Messaging: settings, the APNs token, topic checks, delivery analytics, the
  token call, provisional notification permission, and a notification pushed
  to the Simulator (`xcrun simctl push`) arriving in the foreground handler.
- Performance Monitoring (no emulator exists): traces with metrics and
  attributes, a Python request measured with `HTTPMetric`, inactive traces
  while collection is off, and name checks.

It needs Xcode with an iOS simulator, [uv](https://docs.astral.sh/uv/),
`firebase-tools` and Java 21+ for the emulators. The first run creates a Python
3.13 venv for the e2e functions with uv. It
uses the offline `demo-pyios-firebase` project: no Firebase account or
credentials. `E2E_DEVICE` picks the simulator (default `iPhone 17`). The first
build takes a few minutes; results, the app log and a screenshot land in
`e2e/ios/build/e2e/`.

Unit tests run fake Firebase objects; the end-to-end suite is what catches
mismatches with the real SDK. It found bugs the unit tests could not: Objective-C
getters Rubicon exposes as methods (`is_from_cache`, `NSDate` values), TLS left on
for the Firestore emulator, and the SDK stopping the app for a missing URL scheme.

`tests/test_docs.py` fails if a public function or method has a parameter its
`Args:` docs do not describe (or describes one it does not have).

`tests/typing/check_public_api.py` is type-checked, never run: it uses the
public API the way an app does, asserts what the checker infers, and lists
mistakes the types must keep catching.

The tests run on macOS: Rubicon works there, and fake Firebase objects call
the real callback blocks. They check callbacks, errors, block lifetimes,
transactions, and value conversion. They do not replace testing on a device
with the real Firebase SDK.

