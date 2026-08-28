# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Kept CSRF key material off the public application surface. `Protector` now
  names its ring with an opaque `csrf.Handle` instead of a `*KeyRing`, so
  `*app.App` and `*csrf.Protector` erase to the untyped `ptr` and a server
  integration can carry an application as handler state again.
- Bounded module-private ring registration with generation-checked handles, so
  a handle retained across release never resolves and a reissued slot cannot
  revive it.

### Added

- A compile-time probe asserting every public type erases to `ptr`, and that
  key-owning types keep refusing to.

## [0.4.0] - 2026-08-28

### Added

- Reusable render body and media storage through explicit release.
- Structured request events covering start, finish, errors, cancellation, route,
  status, bytes, and duration, with exactly one start and one terminal event.
- A closed label vocabulary with per-name value domains, fixed label cardinality,
  and explicit reject or elide policies for bounded request fields.
- Middleware outcome and exchange completion mapping onto measured terminal
  events.
- An in-process harness that drives requests, fragmented and suspending request
  bodies, streamed responses, middleware, providers, sessions, admission, and
  lifecycle without a socket, runtime, or HTTP client.
- Caller-owned, overlap-checked harness storage for response fields, trailers,
  informationals, the request arena, and the response capture buffer.
- Case and suite execution against every wire version the HTTP dependency
  exposes, with a first-failure report.

## [0.3.0] - 2026-08-28

### Added

- Caller-owned application composition and deterministic service lifecycle.
- Atomic bounded request admission with graceful drain ownership.
- Generation-bound request contexts over exact `mach-http` exchanges and cancellation scopes.
- Compile-once typed method, host, path, parameter, wildcard, and handler routes.
- Request-scoped text, integer, boolean, UUID, and custom parameter decoding.
- Structured route conflict, malformed target, decoder, capacity, and stale-dispatch errors.
- Immutable middleware snapshots with context-bound, value-typed next tokens.
- Nonreentrant execution claims with deterministic sequential context reuse.
- Deterministic short-circuit, error replacement, and pre-cancelled or timed-out classification.
- Value-owned application and mapper errors with explicit production bounds.
- Strict RFC 3629 public error validation with C0, DEL, and C1 rejection.
- Bounded default error responses that never expose private error details.
- Application-owned middleware depth and process-abort panic policy.
- Strict bounded request Cookie parsing with explicit duplicate-name policy.
- Transactional Set-Cookie serialization with prefix and security enforcement.
- AES-256-GCM and ChaCha20-Poly1305 protected session codecs.
- Explicit entropy, nonce reuse, context binding, clock, rotation, and replay policy.
- Fixation-resistant 256-bit session identifier regeneration.
- Bounded concurrent in-memory sessions with optimistic version and generation checks.
- Injectable lifecycle-owned durable session store and replay guard boundaries.
- Atomic fixation-safe session identity replacement and explicit expired-record
  reclamation.
- Bounded security header defaults with transactional response publication.
- Exact same-origin and allowlist enforcement for unsafe requests.
- HMAC-SHA-256 CSRF tokens bound to session or request generations with bounded
  key rotation and clock windows.
- Authentication principal ownership with deterministic failure and release.
- Transactional relative, same-origin, and allowlisted redirect policy.
- Incremental URL-encoded decoding with independent encoded, field, name,
  value, and temporary-storage limits.
- Fragmented and nested multipart decoding with strict MIME parameter grammar.
- Request-wide asynchronous upload batches with per-file staging and one atomic
  publish or abort decision.
- Explicit durable reconciliation for unknown upload commit and abort outcomes.
- HTTP body adapters that span pending body and storage operations without
  losing token ownership.
- Bounded fixed and pull-streamed response bodies with suspend, resume, and
  cancellation, and no mandatory template engine.
- Explicit media types and charsets serialized once into caller storage.
- Measured HTML and JSON output escaping that rejects invalid UTF-8 and control
  code points and never emits a partial escape.
- Transactional response installation of one status, one content type, and one
  body.
- Generic streaming, server-sent event, and WebSocket channels over one bounded
  compacting queue with a shared send and close vtable.
- Prefix-accepting stream writes and whole-message event and frame writes that
  report a full consumer as backpressure.
- Suspended body reads that resume on the exact producer token, with disconnect
  and cancellation closing a channel fail-closed.
- Strict event stream framing for names, identifiers, retries, multi-line data,
  and comments, with caller-clocked heartbeats.
- WebSocket channels over the `mach-http` codecs with no transport ownership and
  an explicit close code and reason policy.

### Changed

- Pinned `mach-std` to v0.33.0, `mach-http` to v0.4.1, and `mach-crypto` to v0.6.0.
- Routed handler response ownership through the bound request context.
- Required complete allocator callback tables at context binding and allocating boundaries.
- Revalidated response, body, field storage, generation, and cancellation state after allocator callbacks.
- Applied attribute bounds to every standard Set-Cookie member and rejected all
  parser and serializer ownership aliases before mutation.
- Retained nonce and replay claims for their complete cryptographic and accepted
  decode horizons, with distinct guard domains and hardened regeneration ownership.
- Rejected duplicate key material across generations and isolated AEAD nonces
  from mutable guard callback inputs.
- Added complete entropy, guard, codec, key-ring, and store ownership queries
  with fragmented-provider overlap rejection, checked session ranges, and
  overflow-safe initializer products.
- Ordered cookie scalar preflight before traversal and checked every serialized
  length component.
- Bound every key ring to one algorithm and nonce domain, staged callback inputs,
  detected mutated replay claims, and serialized in-memory lifecycle state.
- Rejected cancellation-scope output aliases before store locking and made
  manager ownership and lifecycle transitions atomic and reentrancy-safe.

## [0.2.0] - 2026-08-27

### Changed

- Renamed the framework and repository from `mach-web` to Laurel.
- Renamed the Mach project, artifact, library output, and public module namespace
  from `web` to `laurel`.

The namespace change is intentionally breaking. Consumers must replace `web.*`
imports with `laurel.*` imports.
