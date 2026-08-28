# Application security policy

Laurel separates response hardening, origin enforcement, CSRF protection,
authentication, and redirects. Applications select each policy explicitly and
retain ownership of every backing record. There is no hidden process state or
fallback policy.

## Secure response defaults

`security.secure_headers` initializes the production defaults:

- `Content-Security-Policy: default-src 'self'; object-src 'none'; base-uri
  'self'; frame-ancestors 'none'`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(),
  usb=()`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` on secure
  requests

Custom header policy is accepted only through `security.init_headers`. Every
value is independently bounded and rejects controls, CR, LF, invalid referrer
values, invalid frame options, and unsafe HSTS combinations. HSTS preload
requires subdomains. `apply_headers` rejects an existing managed header and
leaves response status, field count, and byte accounting unchanged on failure.

## Origin policy

An `OriginPolicy` contains a bounded, duplicate-free allowlist of serialized
HTTPS or HTTP origins. Rules contain only a scheme and authority. Userinfo,
paths, queries, fragments, controls, backslashes, and malformed ports are
rejected.

For unsafe methods, the secure default requires exactly one `Origin` field.
The origin must match the request scheme and `Host` or an explicit allowlist
entry. Missing, duplicate, opaque, and malformed origins fail closed. Safe
methods may pass without an origin. Disabling unsafe-method enforcement is an
explicit policy relaxation.

## CSRF tokens

`security.csrf.Protector` emits a fixed 96-byte unpadded base64url token. The
caller supplies a buffer with `TOKEN_CAPACITY`, currently 97 bytes, because a
successful issue operation also writes a trailing null byte. Failure never
changes caller output.

Tokens use HMAC-SHA-256 over a versioned header and the selected external
binding. The header contains the key generation, binding mode, issue time,
request generation, a 128-bit random value, and binding length. The full token
is authenticated before temporal errors are returned.

Two binding modes are available:

- `BIND_SESSION` authenticates a nonempty caller-provided session identifier.
- `BIND_REQUEST` authenticates the exact request identifier and exchange
  generation held by `context.Context`.

A token issued for one binding cannot authenticate under another. CSRF tokens
remain reusable inside their validity window. They are request-forgery tokens,
not replay-prevention credentials.

The entropy provider must fill all requested bytes or return nonzero. It
publishes the size of its primary context and an alias query covering every
region it owns. Provider state, the protector, key ring, key storage, request
context, bindings, tokens, and outputs must be physically disjoint. Provider
descriptor or policy mutation during a callback is detected and fails closed.

Each key generation has a nonzero unique identifier, unique 256-bit secret,
activation time, exclusive issue deadline, and exclusive verification
deadline. At most 16 generations may be retained. `rotate` selects an active
generation without invalidating existing tokens. Verification through a
retired generation returns `needs_rotation`. Token lifetime and clock skew are
bounded independently of key windows. Unknown, inactive, future, expired,
noncanonical, and unauthenticated tokens fail without output publication.

The active ring owns its caller-provided key array until `release_ring`
returns. Applications must not mutate ring fields or key generations directly.
Issue, verify, rotation, and release serialize key access through the ring
mutex. Release zeroizes every secret key and invalidates the ring.

`verify_request` enforces exactly one `x-csrf-token` field for unsafe methods
when `require_unsafe` is enabled. Safe methods pass without a token. Disabling
this requirement is an explicit policy relaxation.

## Authentication ownership

An `Authenticator` supplies exact context size, a complete alias query,
authentication, and principal release callbacks. Authentication accepts one
active request context in `PRINCIPAL_NONE`, transitions it through
`PRINCIPAL_AUTHENTICATING`, and publishes one nonnull principal only after the
callback and descriptor remain stable. Provider errors and empty principals
restore the empty state.

Each accepted principal has exactly one release obligation. Failed release
restores principal ownership so the caller can retry. Successful release moves
the context to `PRINCIPAL_RELEASED`. `app.release_context` performs this release
before unbinding and refuses to discard an owned principal.

## Redirect policy

`RedirectPolicy` permits relative destinations, same-origin absolute
destinations, and allowlisted absolute destinations only when enabled.
Scheme-relative paths, controls, backslashes, userinfo, unsafe schemes, and
malformed locations are rejected. Redirect status and the `Location` field are
published together. Existing `Location` fields and capacity failure leave the
response unchanged.

## Request order

A production request path should check origin policy, authenticate when the
route requires identity, verify CSRF for unsafe state changes, execute the
handler, apply security headers to every final response, and release the
request context. Error responses receive the same security headers. Any policy
relaxation should be represented in application configuration and reviewed as
part of deployment policy.
