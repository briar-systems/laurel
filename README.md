# Laurel

Laurel is a lightweight production web application framework for Mach. It defines the application layer above `mach-http` while keeping protocol parsing, transport ownership, application dispatch, and integration policy in separate packages.

The application foundation is implemented. Applications assemble caller-owned providers, limits, handlers, observers, security policy, and lifecycle callbacks. Startup, readiness, admission, drain, stop, and failure cleanup are deterministic. Each admitted request context borrows one exact `mach-http` exchange generation and cancellation scope.

Production scope includes typed handlers, middleware, secure sessions and cookies, forms, streamed uploads, rendering, service providers, application lifecycle, structured failures, observability, in-process tests, streaming responses, server-sent events, and WebSockets. Database clients, template engines, queues, and identity systems remain replaceable providers rather than mandatory framework subsystems.

The framework has no global application registry, hidden allocator, mandatory template language, mandatory persistence layer, or server-specific connection state.

## Boundaries

- `app` owns assembled framework configuration and application state.
- `context` carries one borrowed exchange, generation-bound route parameters, request identity, cancellation scope, allocator, and application state.
- `handler` defines application handlers over an explicit context and response.
- `router` compiles typed framework routes into caller-owned `mach-http` matcher storage and decodes parameters from the request scope.
- `middleware` executes an application-owned, request-scoped chain with single-use next handlers.
- `error` classifies application failures and maps them to bounded fail-closed HTTP responses.
- `session` separates session lifecycle, protected cookie encoding, and durable storage.
- `security` defines response header, CSRF, origin, and authentication policy hooks.
- `form` and `upload` keep bounded parsing and streamed file storage separate.
- `render` converts a model into a response body without coupling the framework to a template engine.
- `observability` reports request events through application-owned logging and metrics callbacks.
- `testing` defines an in-process request harness boundary.
- `cookie` defines bounded request and response cookie storage.
- `provider` injects application services without a global container.
- `lifecycle` owns application startup, readiness, drain, and shutdown.
- `realtime` covers streaming responses, server-sent events, and WebSockets.

## Local dependencies

The manifest uses pinned Git tags for `mach-std` v0.29.0 and `mach-http` v0.3.0. Build output uses Mach's default `out/` directory.

## Status

Application composition, lifecycle, bounded admission, exact request-context ownership, compile-once typed routes, request-scoped parameter decoding, stale-dispatch rejection, single-pass middleware, cancellation unwinding, and fail-closed error rendering are implemented. Protected sessions, security defaults, forms, uploads, rendering, realtime responses, and the in-process harness remain tracked work. Security-sensitive operations have no fallback implementation. The route ownership and decoder contract is documented in [`doc/routing.md`](doc/routing.md). Middleware ordering and error ownership are documented in [`doc/middleware.md`](doc/middleware.md).
