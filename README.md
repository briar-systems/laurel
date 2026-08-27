# Laurel

Laurel is a lightweight production web application framework for Mach. It defines the application layer above `mach-http` while keeping protocol parsing, transport ownership, application dispatch, and integration policy in separate packages.

The current repository is a contract scaffold. It defines stable ownership and extension boundaries without pretending that route dispatch, middleware execution, session protection, multipart parsing, or rendering already work.

Production scope includes typed handlers, middleware, secure sessions and cookies, forms, streamed uploads, rendering, service providers, application lifecycle, structured failures, observability, in-process tests, streaming responses, server-sent events, and WebSockets. Database clients, template engines, queues, and identity systems remain replaceable providers rather than mandatory framework subsystems.

The framework has no global application registry, hidden allocator, mandatory template language, mandatory persistence layer, or server-specific connection state.

## Boundaries

- `app` owns assembled framework configuration and application state.
- `context` carries one borrowed request, route parameters, request identity, cancellation state, and application state.
- `handler` defines application handlers over an explicit context and response.
- `router` connects framework handlers to caller-owned `mach-http` router storage.
- `middleware` defines an allocation-free chain contract with explicit next handlers.
- `error` classifies application failures and maps them to HTTP responses.
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

The manifest uses pinned Git tags for `mach-std` and `mach-http`. Build output uses Mach's default `out/` directory.

## Status

This scaffold is not a runnable framework. Security-sensitive operations have no fallback implementation. A production release requires the corresponding `mach-http` server lifecycle, a reviewed session codec, bounded form and multipart parsers, and concrete error and observability adapters.
