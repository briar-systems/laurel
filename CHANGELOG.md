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

### Changed

- Pinned `mach-std` to v0.29.0 and `mach-http` to v0.3.0.
- Routed handler response ownership through the bound request context.
- Required complete allocator callback tables at context binding and allocating boundaries.
- Revalidated response, body, field storage, generation, and cancellation state after allocator callbacks.

## [0.2.0] - 2026-08-27

### Changed

- Renamed the framework and repository from `mach-web` to Laurel.
- Renamed the Mach project, artifact, library output, and public module namespace
  from `web` to `laurel`.

The namespace change is intentionally breaking. Consumers must replace `web.*`
imports with `laurel.*` imports.
