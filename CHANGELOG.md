# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Incremental URL-encoded decoding with independent encoded, field, name,
  value, and temporary-storage limits.
- Fragmented and nested multipart decoding with strict MIME parameter grammar.
- Request-wide asynchronous upload batches with per-file staging and one atomic
  publish or abort decision.
- Explicit durable reconciliation for unknown upload commit and abort outcomes.
- HTTP body adapters that span pending body and storage operations without
  losing token ownership.

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
