# Laurel

Laurel is a lightweight production web application framework for Mach. It defines the application layer above `mach-http` while keeping protocol parsing, transport ownership, application dispatch, and integration policy in separate packages.

The application foundation is implemented. Applications assemble caller-owned providers, limits, handlers, observers, security policy, and lifecycle callbacks. Startup, readiness, admission, drain, stop, and failure cleanup are deterministic. Each admitted request context borrows one exact `mach-http` exchange generation and cancellation scope.

Production scope includes typed handlers, middleware, secure sessions and cookies, forms, streamed uploads, rendering, service providers, application lifecycle, structured failures, observability, in-process tests, streaming responses, server-sent events, and WebSockets. Database clients, template engines, queues, and identity systems remain replaceable providers rather than mandatory framework subsystems.

The framework has no global application registry, hidden allocator, mandatory template language, mandatory persistence layer, or server-specific connection state. Its one piece of process-wide state is a bounded module-private table inside `security.csrf` that maps an opaque handle to a caller-owned key ring, which is what keeps key material off every public type. See [`doc/security.md`](doc/security.md).

## Boundaries

- `app` owns assembled framework configuration and application state.
- `context` carries one borrowed exchange, generation-bound route parameters, request identity, cancellation scope, allocator, and application state.
- `handler` defines application handlers over an explicit context and response.
- `router` compiles typed framework routes into caller-owned `mach-http` matcher storage and decodes parameters from the request scope.
- `middleware` snapshots and executes an application-owned chain with value-typed, single-use next handlers.
- `error` owns bounded failure text and maps strict UTF-8 public messages to fail-closed HTTP responses.
- `session` separates session lifecycle, protected cookie encoding, and durable storage.
- `security` defines bounded response headers, origin enforcement,
  HMAC-protected CSRF tokens addressed by an opaque handle so key material
  never reaches a public type, authentication ownership, and redirect policy.
- `form`, `multipart`, and `upload` keep bounded parsing, request-wide upload
  transactions, and streamed file storage separate.
- `render` converts a model into a bounded response body, with explicit media
  type, charset, and escaping, and no coupling to a template engine.
- `observability` reports one start and one terminal request event through
  application-owned callbacks, with fixed label cardinality and field bounds.
  `app` drives the recorder over the assembled observer, so admitting a request
  emits its start event and releasing it emits its terminal event.
- `testing` drives a whole application in process, with no socket, runtime, or
  client, across every wire version the HTTP dependency exposes.
- `cookie` defines bounded request and response cookie storage.
- `provider` injects application services without a global container.
- `lifecycle` owns application startup, readiness, drain, and shutdown.
- `realtime` covers streaming responses, server-sent events, and WebSockets over
  one bounded queue with explicit backpressure, heartbeat, and close policy.

## Local dependencies

The manifest uses pinned Git tags for `mach-std` v0.33.0, `mach-http` v0.4.1,
and `mach-crypto` v0.6.0. Build output uses Mach's default `out/` directory.

## Status

Application composition, lifecycle, bounded admission, exact request-context
ownership, typed routes, immutable middleware execution, value-owned errors,
strict cookies, AEAD-protected sessions, bounded replay and nonce guards,
generation-safe in-memory persistence, atomic session identity replacement,
expired-record reclamation, ownership-safe manager lifecycle, the durable
store boundary, secure response defaults, origin enforcement, HMAC-protected
session or request-bound CSRF tokens, authentication ownership, and safe
redirects are implemented. Bounded URL-encoded forms, fragmented and nested
multipart decoding, streamed files, atomic request-wide upload batches,
cancellation, and durable outcome reconciliation are implemented. Bounded fixed
and streamed response bodies, explicit media types and output escaping, generic
streams, server-sent events, and WebSocket channels are implemented. Structured
request events with fixed label cardinality and bounded fields, and the
in-process harness for requests, streaming bodies, middleware, providers,
sessions, and lifecycle, are implemented.
Security-sensitive operations have no fallback implementation. See
[`doc/routing.md`](doc/routing.md), [`doc/middleware.md`](doc/middleware.md),
[`doc/sessions.md`](doc/sessions.md), [`doc/security.md`](doc/security.md),
[`doc/input.md`](doc/input.md), [`doc/output.md`](doc/output.md), and
[`doc/observability.md`](doc/observability.md) for the ownership contracts.
