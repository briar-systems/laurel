# Laurel

Laurel is a lightweight production web application framework for Mach. It defines the application layer above `mach-http` while keeping protocol parsing, transport ownership, application dispatch, and integration policy in separate packages.

The application foundation is implemented. Applications assemble caller-owned providers, limits, handlers, observers, security policy, and lifecycle callbacks. Startup, readiness, admission, drain, stop, and failure cleanup are deterministic. Each admitted request context borrows one exact `mach-http` exchange generation and cancellation scope.

Production scope includes typed handlers, middleware, secure sessions and cookies, forms, streamed uploads, rendering, service providers, application lifecycle, structured failures, observability, in-process tests, streaming responses, server-sent events, and WebSockets. Database clients, template engines, queues, and identity systems remain replaceable providers rather than mandatory framework subsystems.

The framework has no global application registry, hidden allocator, mandatory template language, mandatory persistence layer, or server-specific connection state. Its only process-wide state is three bounded module-private tables: one inside `security.csrf` that maps an opaque handle to a caller-owned key ring, one inside `secret` that maps an opaque source to a host-owned secret resolver, and one inside `serve` that holds each host's environment resolver. They are what keep key material off every public type. See [`doc/security.md`](doc/security.md) and [`doc/providers.md`](doc/providers.md).

## Boundaries

- `app` owns assembled framework configuration and application state.
- `context` carries one borrowed exchange, generation-bound route parameters, request identity, cancellation scope, allocator, and application state.
- `handler` defines application handlers over an explicit context and response.
- `router` compiles typed framework routes into caller-owned `mach-http` matcher storage and decodes parameters from the request scope.
- `middleware` snapshots and executes an application-owned chain with value-typed, single-use next handlers.
- `error` owns bounded failure text and maps strict UTF-8 public messages to fail-closed HTTP responses.
- `session` separates session lifecycle, protected cookie encoding, and durable
  storage, and reaches a request through `session.Binder` middleware that loads
  lazily and commits one `Set-Cookie` from the assembled policy.
- `security` defines bounded response headers, origin enforcement,
  HMAC-protected CSRF tokens addressed by an opaque handle so key material
  never reaches a public type, authentication ownership, and redirect policy.
- `form`, `multipart`, and `upload` keep bounded parsing, request-wide upload
  transactions, and streamed file storage separate.
- `query` decodes a request's query string with the form decoder, and `raw`
  reads a whole request body as its exact bytes under a caller limit.
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
- `task`, `config`, and `secret` define the facilities a host supplies:
  background tasks with single-flight triggers, snapshots read without waiting,
  and a bounded drain; read-only configuration; and secrets borrowed for one
  call through a public source. `observability.Telemetry` carries application
  signals outside a request. `task.runner` is the task provider both hosts
  run, stepped by hand under `testing` and from its own thread under `serve`.
  See [`doc/providers.md`](doc/providers.md).
- `serve` runs an application standalone on mach-http's server runner, with
  built-in providers and a bounded drain on SIGTERM or SIGINT. See
  [`doc/serve.md`](doc/serve.md).
- `lifecycle` owns application startup, readiness, drain, and shutdown. It
  preserves the primary failure while exposing any later shutdown cleanup
  failure through `app.cleanup_failure`.
- `realtime` covers streaming responses, server-sent events, and WebSockets over
  one bounded queue with explicit backpressure, heartbeat, and close policy.

## Hosting

An application is written once, against the providers its host supplies, and
never names its host.

- **Standalone.** `laurel.serve` runs it on mach-http's HTTP/1.1 server runner,
  behind any proxy that terminates TLS. The host supplies a task runner on its
  own thread, configuration and secrets from the environment, and telemetry on
  stderr, each replaceable, and drives the lifecycle through the server's
  start, ready, drain and stop hooks. SIGTERM or SIGINT drains it to a bounded
  deadline. [`demo/standalone/`](demo/standalone/) is a complete example, and
  [`doc/serve.md`](doc/serve.md) the contract.

  ```mach
  var host: serve.Host;
  serve.init(?host, serve.options_default());
  my_app.assemble(?state, serve.providers(?host));
  serve.run(?host, ?state.application, serve.config_default(address));
  ```

- **Inside a server.** hedge hosts it in process, beside static files and
  proxied upstreams, through a binding that feeds laurel's providers from the
  server's facilities. [`demo/`](demo/) is an application hosted by hedge across
  several workers beside a static file and a health check. Its README states
  what one application shared by every worker must guarantee.

The same `assemble` also runs in process under `laurel.testing`, over the same
providers, which is how [`demo/standalone/`](demo/standalone/) tests itself.

Standalone, `realtime` WebSocket sessions run over the server's tunnel, and a
streamed response such as server-sent events lives as long as it makes progress.

## Benchmarks

[`doc/bench/`](doc/bench/) measures the same three-route service written in
Laurel, in Go on `net/http`, and in Rust on axum, and publishes the measured
results. [`doc/bench/COMPARISON.md`](doc/bench/COMPARISON.md) sets the three
side by side on performance and on ergonomics, including where Laurel loses.

## Local dependencies

The manifest selects releases by version range, with the resolved release
committed as a gitlink under `dep/`, and builds with mach 6: `mach-std` `^9.0`
(v9.0.0), `mach-http` `^0.24` (v0.24.0) and `mach-crypto` `^0.24` (v0.24.0).
Build output uses Mach's default `out/` directory.

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
[`doc/observability.md`](doc/observability.md), and
[`doc/lifecycle.md`](doc/lifecycle.md) for the ownership contracts.
