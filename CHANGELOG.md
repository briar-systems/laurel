# Changelog

## [Unreleased]

### Added
- `query.decode` and `query.parse` decode a query string with the one `form.UrlEncoded` decoder, so percent escapes, `+` as a space, strict UTF-8, repeated keys and empty values behave as they do in a form body (#163). `form.init_source` names what the decoder reads: a malformed query is 400 `malformed query` and one past its limits is 400 `query is too large`, where a form body keeps 400 `malformed form` and 413 `form is too large`.
- `form.find`, `form.find_next` and `form.typed` read a decoded form or query: the first field with a name, every later value of a repeated key in wire order, and one value through a `router.Decoder`, the same decoders that type path parameters (#163).
- `raw.Body` reads a whole request body as its exact bytes into a caller buffer under a caller limit, suspending on the host like the form and multipart parsers (#163). A body over the limit is `raw.LIMIT` with 413, whether its declared length says so before any byte is read or an unsized body reaches the limit, a sized body that ends short of or past its length is `raw.MALFORMED` with 400, and every failure zeroes what was read.
- `testing.Request.chunked` presents a request body with no declared length, as HTTP/1.1 chunked coding and HTTP/2 or HTTP/3 data without `content-length` reach the application (#163). `testing.request` sets it false, and a `testing.Request` literal must now name it.

### Changed
- **Breaking.** Dependencies: http `^0.20` at v0.20.0 (was `^0.19` at v0.19.0). Resolution is flat, so a consumer must move to http 0.20 with it. http 0.20's router refuses a target whose query is not well formed, such as `?q=%zz`, with `DISPATCH_TARGET` before any route runs, and `router.dispatch` answers it as 400 `malformed query` with `error.BAD_REQUEST`, the answer the query decoder gives. Without that mapping it would have been 500 `route dispatch failed`. http 0.20's other changes are in the h1 server engine and `core.target`, which the host drives. demo/ and doc/bench/laurel/ keep their hedge v0.6.0 pins until hedge moves (#171).

### Fixed
- The README's dependency section names the current ranges and releases. It still named std v0.34.0, http v0.7.5 and crypto v0.8.1 (#171).
- The in-process harness answers a body read with no allowance left the way a host does, so a request body past the configured `request_body.max_bytes` ends in the reader's limit rather than a provider failure (#163).

## [0.17.0] - 2026-09-25

### Changed
- **Breaking.** Dependencies: std `^8.0` at v8.0.0 (was `^7.0` at v7.0.2), crypto `^0.22` at v0.22.0 (was `^0.20` at v0.20.0) and http `^0.19` at v0.19.0 (was `^0.18` at v0.18.0), and `mach.toml` requires mach `^5.12` (was `^5.9`), which std 8 requires (#164). Resolution is flat, so a consumer must move to std 8.x and mach 5.12 with it. std 8 adds the typed secret view and grows `buffers.SecretSource`, which laurel does not use. crypto 0.21 adds keyed AES-GCM contexts and keeps `aes_gcm.seal` and `open`, the only AES-GCM calls laurel makes, and http 0.19 changes only the h2 engine, which laurel does not use. Rebuild from a clean `out/`, as std's release notes say. CI seeds mach v5.12.0, ahead of the family pin. Under mach 5.12 `mach test .` covers only the library's closure, and the library reaches every module that holds a test, so the same 115 tests run. demo/ and doc/bench/laurel/ keep their hedge v0.6.0 pins until hedge moves.

## [0.16.1] - 2026-09-23

### Changed
- Dependencies: http `^0.18` at v0.18.0 (was `^0.17` at v0.17.0), so laurel resolves alongside a project that needs http 0.18 (#158). http 0.18 adds `h2.connection.pending_work` and fixes an HTTP/2 frame dropped at the peer's end of stream, and laurel uses neither the h2 engine nor anything else that changed. std and crypto are unchanged. demo/ and doc/bench/laurel/ keep their hedge v0.6.0 pins until hedge moves.

## [0.16.0] - 2026-09-22

### Changed
- **Breaking.** Dependencies: std `^7.0` at v7.0.2 (was `^6.0` at v6.0.0), crypto `^0.20` at v0.20.0 (was `^0.18` at v0.18.0) and http `^0.17` at v0.17.0 (was `^0.15` at v0.15.0) (#154). A consumer must be on std 7.x as well. Nothing in std 7's migration guide reaches laurel's code: it has no `io.runtime.make` caller, uses no `data.toml`, and of `std.allocator` uses only `allocate` and `fixed`, never `page`, `testing`, `arena` or `heap`. crypto 0.19 and 0.20 change P-256, P-384, RSA and Poly1305 internals only, and http 0.16 and 0.17 add closure reporting and the std bump without changing the surface laurel uses. demo/ and doc/bench/laurel/ keep their hedge v0.6.0 pins until hedge moves.

## [0.15.0] - 2026-09-19

### Changed
- **Breaking.** Dependencies: std `^6.0` at v6.0.0 (was v5.3.0), crypto `^0.18` at v0.18.0 (was v0.13.2) and http `^0.15` at v0.15.0 (was v0.12.0), and `mach.toml` requires mach `^5.9` (#150). A consumer must be on std 6.x as well. Nothing in std 6's migration guide reaches laurel's code: it uses no `sort`, `heap`, `map` or `set`, no width-named `ct` comparison (its three `ct.eq_bytes` sites are unchanged) and no buffer account, and http 0.15's own surface is unchanged. CI asks the family workflow for `dit: required`, because crypto 0.18 links std's start code that turns PSTATE.DIT on for aarch64 programs. demo/ and doc/bench/laurel/ keep their hedge v0.6.0 pins, which hold them on std 5, until hedge moves.
- demo/ and doc/bench/laurel/ pin hedge v0.6.0, laurel v0.14.0, mach-std v5.4.0 and mach-http v0.13.2, and follow hedge's growable connection storage (#110). `serve.make` takes no pool: the caller-provided slot and connection arrays are gone, and `server.limits.max_connections` is left unset in both `hedge.toml` because it is a policy cap now rather than a storage size. Both programs host the application through `hedge.service.laurel` instead of their own copy of the seam (`src/host.mach` is removed): the adapter dispatches through the application's router, resumes a suspended handler and enforces the handler deadline, so the reasons for the copy no longer hold. The form handlers suspend on the request body (`handler.suspend`) and resume where they left off, following laurel 0.11, and the manifests move to laurel 0.14's `Instant` and `handler_timeout` shapes.
- The tag-triggered workflow is `.github/workflows/cd.yml`, renamed from `release.yml` with no content change, matching the family layout (#147).
- demo/ and doc/bench/laurel/ declare `mach = "^5.3"` like the root manifest (#143).

## [0.14.0] - 2026-09-17

### Changed
- **Breaking.** Dependencies: std v5.3.0 (was v4.0.1), crypto v0.13.2 (was v0.12.0) and http v0.12.0 (was v0.11.0), and `mach.toml` requires mach `^5.3` (#139). A consumer must be on std 5.x as well. laurel consumes no std io completion and uses none of http's transport or h1, h2 and h3 engines, so neither std 5.3's cancelled-completion transfers nor http's borrowed per-request memory reach its own code. Rebuild from a clean `out/`, since std changed record layouts without changing signatures.
- **Breaking.** Every instant and deadline is a monotonic `time.Instant`, and the one relative bound is a `Duration` (#139). A wall-clock `time.Time` or a raw integer no longer type-checks in any of these places. Old and new, side by side:

  | before | after |
  | --- | --- |
  | `app.Admission.started_ns: i64` | `app.Admission.started: time.Instant` |
  | `app.Termination.now_ns: i64` | `app.Termination.finished: time.Instant` |
  | `app.Limits.handler_deadline_ns: i64` (`lifecycle.NO_DEADLINE` for none) | `app.Limits.handler_timeout: opt[duration.Duration]` |
  | `app.drain(app, deadline_ns: i64)` | `app.drain(app, deadline: opt[time.Instant])` |
  | `lifecycle.drain(controller, deadline_ns: i64)` | `lifecycle.drain(controller, deadline: opt[time.Instant])` |
  | `lifecycle.DrainFun: fun(ptr, i64)` | `lifecycle.DrainFun: fun(ptr, opt[time.Instant])` |
  | `lifecycle.NO_DEADLINE` | removed, use `opt[...].none{}` |
  | `context.deadline(ctx, *time.Time)` | `context.deadline(ctx, *time.Instant)` |
  | `context.narrow_deadline(ctx, time.Time)` | `context.narrow_deadline(ctx, time.Instant)` |
  | `observability.begin(..., started_ns: i64)` | `observability.begin(..., started: time.Instant)` |
  | `observability.finish`, `cancelled`, `failed`, `observe_execution` take `now_ns: i64` | they take `finished: time.Instant` |
  | `observability.RequestEvent.started_ns: i64` | `observability.RequestEvent.started: time.Instant` (`duration_ns` is unchanged) |
  | `testing.Request.deadline_ns: i64` (`testing.NO_DEADLINE` for none) | `testing.Request.deadline: opt[time.Instant]` |
  | `testing.drain(harness, deadline_ns: i64)` | `testing.drain(harness, deadline: opt[time.Instant])` |
  | `testing.NO_DEADLINE` | removed |
  | `realtime.Policy.heartbeat_interval_ns: i64` | `realtime.Policy.heartbeat_interval: duration.Duration` |
  | `realtime.init_stream` and `init_socket` take `start_ns: i64` | they take `start: time.Instant` |
  | `realtime.stream_heartbeat`, `stream_observe`, `socket_heartbeat` and `socket_observe` take `now_ns: i64` | they take `now: time.Instant` |

  Wall-clock time is unchanged where a value is compared with something that outlives the process: cookie `expires_unix` and the session and csrf key-ring clocks.
- The copyright holder is now Briar Systems LLC (#137). The MIT license text is unchanged.

## [0.13.3] - 2026-09-17

### Changed
- The http pin advances to v0.11.0 (#133). That release adds `h1.connection.next_deadline` and documents that every http deadline is monotonic time. std v4.0.1 and crypto v0.12.0 are unchanged.

## [0.13.2] - 2026-09-17

### Security
- `app.Limits.handler_deadline_ns` is now applied (#126). Before this release it was validated and then ignored, so an application that set it had no handler timeout at all. `app.bind_context` narrows the request deadline to `Admission.started_ns + handler_deadline_ns`, never widening a deadline the exchange scope already carries, and `context.deadline` returns the earlier of the two. The host arms its own timer from `context.deadline` and times out the exchange scope. laurel reads no clock itself and never assumes std fires the deadline. A `started_ns` that is negative, or too large to add the limit to, fails the bind.

### Changed
- Every deadline laurel accepts or exposes is documented as an absolute monotonic instant: `Admission.started_ns`, `context.deadline`, `testing.Request.deadline_ns` and `lifecycle.drain`'s `deadline_ns` (#126). A deadline built from wall time never fires (hedge#168). `Admission.started_ns` changes from `i64` to std's `Instant` in the std 5 migration.

## [0.13.1] - 2026-09-17

### Changed
- The crypto pin advances to v0.12.0, which brings faster X25519 and Ed25519 (#125).
- Releases are published by `release.yml` when a `v*` tag is pushed, through the shared family release workflow (#123). It verifies the tag against the manifest and the changelog, runs the full CI tier, and publishes the GitHub release with this changelog's section as its notes. A dispatch of `release.yml` rehearses the same path without a tag.

## [0.13.0] - 2026-09-17

### Changed
- **Breaking.** Dependencies: the std pin advances to v4.0.1, the crypto pin to v0.11.0 and the http pin to v0.10.0 (#119). std 4 requires mach 5.2.0 or later, and a consumer must be on std 4.x as well. Laurel builds no std io errors, branches on no std error kind or code, and holds no socket, so its own source is unchanged.

## [0.12.0] - 2026-09-16

### Changed
- The std pin advances to v3.2.0, the crypto pin to v0.10.1 and the http pin to v0.9.0 (#115). Laurel does not use the std io surfaces that changed in 3.x, so no source changes were needed.
- CI runs the shared family pipeline from briar-systems/.github behind a single `gate` check (#111). A pull request into `dev` runs the light tier on x86_64-linux, a pull request into `main` adds the native aarch64-linux, x86_64-windows, aarch64-darwin and x86_64-darwin legs, and nothing runs on push. The format check is now enforced, and demo/ and doc/bench/laurel/ are built on every run.

## [0.11.0] - 2026-09-16

### Added
- A handler can suspend on request body I/O and be resumed (#96). `handler.suspend(token)` leaves the chain, `app.execute` returns `EXECUTION_PENDING` carrying that token, and `app.resume` re-enters only the suspended step. `app.abandon` winds a suspended request up when resumption will never come. A streaming upload no longer has to be buffered in the host before the application is entered.

### Changed
- **Breaking.** A middleware is now two halves and a resume rather than one callback holding a `Next` token: `Middleware{ctx, before, resume, after}` (#96). `middleware.Next`, `middleware.MiddlewareFun` and `middleware.call` are removed, along with the whole class of token misuse they made possible. `after` runs exactly once for every `before` that ran, including a short circuit, a cancellation and an abandonment, and each step owns one driver-held state slot instead of a native stack frame. See the migration notes in `doc/middleware.md`.
- **Breaking.** A handler returns `handler.Result`, a `Disposition` of `RESPOND`, `NEXT` or `PENDING` with a token, and takes a state out slot: `fun(ptr, *context.Context, *ptr) handler.Result` (#96). `handler.Handler` and every `router.Route` handler gain a `resume` callback, which is `nil` for a handler that never suspends.
- **Breaking.** `app.execute` takes a `*middleware.Execution` the host owns per exchange, because a suspended execution outlives the call that started it (#96).
- `observability.observe_execution` refuses `EXECUTION_PENDING` rather than describing a suspended request as a terminated one (#96).
- demo/ and doc/bench/laurel/ pin hedge v0.4.1.
- demo/ and doc/bench/laurel/ pin laurel v0.10.0 and end their middleware chains through `router.terminal_handler` instead of each carrying the mapping (#105).
- The std pin advances to v2.2.0 and the crypto pin to v0.9.2.

## [0.10.0] - 2026-09-15

### Added
- `router.Terminal`, `router.terminal` and `router.terminal_handler`: the mapping from a dispatch status to what runs at the end of a middleware chain, which every host was writing for itself (#98). A terminal holding no dispatch returns an internal error naming that instead of a failure with no error in it.

### Changed
- demo/ and doc/bench/laurel/ pin laurel v0.9.2, hedge v0.4.0, mach-http v0.8.2 and mach-std v2.1.0, and each host completes the body read it suspended rather than waiting for hedge to do it (#97).
- The demo is run with `mach dep pull`, `mach build` and `mach run` instead of `demo/run.sh`, which is removed (#101). Its README no longer describes the arena as a fixed 12 KiB: an application declares what it needs when it registers.

## [0.9.2] - 2026-09-15

### Fixed
- A session cookie whose policy has `max_age` 0 omits `Max-Age`, so the browser keeps it for the session instead of deleting it (#82).
- Rendered responses and default error rendering take their limits from the bound exchange through `context.limits`, and a response whose reader limits or length exceed the host's limits returns `RESPOND_LIMIT` instead of failing at commit (#83).

### Changed
- Dependencies: mach-crypto v0.9.1, mach-http v0.8.2.

## [0.9.1] - 2026-09-13

### Changed
- demo/ and doc/bench/laurel/ build on mach 5.0 against hedge v0.3.0 (#89).

## [0.9.0] - 2026-09-13

### Changed
- Migrated to mach 5.0 and mach-std 2.0.0.
- `laurel.router` stays on `res[u8, str]` matching `http.router`.
- Dependencies: mach-crypto v0.9.0, mach-http v0.8.0.

## [0.8.10] - 2026-09-05

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Added

- The demo and the benchmark project pin hedge v0.2.1 and laurel v0.8.9, so they run on the hedge that carries the Nagle, QUIC pool and no-ALPN fixes.

### Changed

- Dependencies: hedge v0.2.1, laurel v0.8.9, mach-http v0.7.6, mach-tls v0.2.5, mach-quic v0.5.9, mach-acme v0.1.9, mach-crypto v0.8.2.

## [0.8.9] - 2026-09-05

### Removed

- `tools/partial_literal_sweep.py`. It enumerated record literals naming fewer
  fields than their record declares, which is a workaround for
  briar-systems/mach#3108; that defect is being fixed in the compiler. The rule
  itself still holds, and `doc/middleware.md` still states it.

### Added

- GitHub Actions CI: every pull request builds the library, runs the suite in both profiles, and verifies IR across all six targets.
- `demo/`, a runnable example application hosted by hedge, and `doc/bench/`, a benchmark project comparing the same three-route service in Laurel, Go `net/http`, and axum, with a published first run and a comparison of performance and ergonomics.

### Changed

- Dependencies: mach-http v0.7.6, mach-crypto v0.8.2.

## [0.8.8] - 2026-09-02

### Changed

- `mach-http` advances to `v0.7.5`, adopting the HTTP/3 DATA frame fix so
  every consumer in hedge's graph shares one release.

## [0.8.7] - 2026-09-02

### Fixed

- The changelog now records the 0.8.6 release, which the release commit had
  omitted.

## [0.8.6] - 2026-09-02

### Changed

- `mach-http` advances to `v0.7.4`, adopting the HTTP/3 teardown fix so
  every consumer in hedge's graph shares one release.

## [0.8.5] - 2026-09-01

### Changed

- `mach-std` advances to `v0.34.0`, `mach-http` to `v0.7.3`, and `mach-crypto`
  to `v0.8.1`, aligning on the released typed secret-storage stack.

## [0.8.4] - 2026-09-01

### Changed

- Pinned `mach-http` to v0.7.2 for generation-safe HTTP/1 and HTTP/2 teardown.

### Fixed

- The partial-literal audit now parses inline record declarations without
  swallowing the declaration that follows them.

## [0.8.3] - 2026-08-31

### Changed

- Pinned `mach-crypto` to v0.7.0.

## [0.8.2] - 2026-08-31

- Expose a shutdown cleanup failure through `lifecycle.cleanup_failure` and
  `app.cleanup_failure`. The primary failure remains the result returned by
  `stop`, while the later cleanup failure remains available to the application.

## [0.8.1] - 2026-08-29

### Fixed

- Set every field of every record literal. A partial literal leaves the fields it
  does not name holding the previous stack frame's contents, not zero
  (briar-systems/mach#3108). The exposure was the public contract rather than
  laurel's own code: `cookie.serialize_set_cookie` returns a two-field
  `Operation` and left `written` unset on all thirty-two failure paths, so an
  application reading a length without checking the status would have got stack
  contents, and a length is a bound. No caller inside laurel read an unnamed
  field.

### Added

- `tools/partial_literal_sweep.py`, which enumerates partial literals from
  record definitions with module qualifiers resolved, and a test pinning that a
  refused `serialize_set_cookie` reports `written == 0` even when the stack it
  builds on is dirty.

## [0.8.0] - 2026-08-29

### Added

- A request-level session boundary, completing #4. `session.Binder` is
  application middleware that loads lazily, so a handler reaches its session
  through `session.from_context` and never drives `cookie.parse_request`, the
  codec, or the store itself. `create_request`, `write_request`,
  `regenerate_request`, and `destroy_request` record intent; the binder commits
  once on the way out, before the response is committed, emitting one
  `Set-Cookie` from the assembled `CookiePolicy`.
- Absence is a state rather than a nil that reads as a value: `request_state`
  distinguishes idle, absent, present, dirty, and destroyed, and a rejected
  token is distinguishable from a missing one.
- `context.Context.session` returns, now set by the binder and read through an
  accessor, which is what its removal in #36 anticipated.

### Changed

- `session.Manager` carries the authenticated context the codec binds each token
  to, so `init_manager` takes it. It is application-scoped, not per-request.
- `session.Codec` gains a `regenerate` slot, so identity replacement is
  reachable behind the manager rather than only on a concrete `ProtectedCodec`.

### Fixed

- Replaced all thirty-five uses of the `T{}` empty record literal, a construct
  briar-systems/mach#3108 calls unreliable. The sites that mattered were
  `memory_store`, `memory_guard`, and `protected_codec`, whose failure paths
  hand back function-pointer tables: a caller detecting the failure by testing a
  callback against nil, the way `app.valid_observer` does, could have received a
  garbage pointer and called it. Latent rather than live — a probe of all three
  passed in both profiles before the change — and fixed because the construct is
  documented as unreliable and the failure would land on a security provider.

### Added

- `error.no_error`, the absence of a failure for outcomes carrying an `AppError`
  slot they do not use. `AppError` and `RenderFailure` hold byte arrays, so
  neither can take a named-field literal; both now clear their bytes explicitly,
  matching what `error.make_view` already did.
- A test pinning that the three provider constructors return no callable pointer
  when handed invalid storage.

### Removed

- `context.Context.session`. It was assigned nil on every path and read nowhere,
  so a host reading `Context` to find what a request carries got a silent wrong
  answer instead of a compile error. Wiring it would mean first designing the
  request-level session boundary, which does not exist yet; `doc/sessions.md`
  now says so plainly and says what an application drives instead.

## [0.7.1] - 2026-08-29

### Fixed

- Closed every admitted request with a terminal event. When the `app.Termination`
  handed to `release_context` was one the recorder refused — a `now_ns` below the
  start time, or an outcome outside the middleware execution vocabulary — the
  request was released with a start event and no terminal, which reads as a
  request still in flight.

### Added

- `observability.OUTCOME_UNREPORTED` and `observability.unreported`, which close a
  started recorder the host could not describe. A distinct outcome rather than
  `OUTCOME_FAILED`, so a consumer does not count failures that never happened.
- Compile-time erasure probes for `app.Admission` and `app.Termination`, beside
  the ones added for the key-handle work.

## [0.7.0] - 2026-08-29

### Fixed

- Connected request events to the assembled observer. `app.App` stored an
  observer that nothing read, so every event reached the in-process harness and
  no production host. `app.bind_context` now emits the start event as it admits
  a request and `app.release_context` emits the one terminal event as it
  releases it, both over the observer the application already holds.
- Masked the whole low nibble in the urlencoded decoder invariant. `!=` binds
  tighter than `&` in Mach, so the check inspected bit 0 alone and accepted
  seven of the fifteen dirty nibbles it was written to reject.

### Changed

- `app.Assembly` takes the label `vocabulary` and the `event_policy` alongside
  the observer, because an application cannot build a recorder without them.
- `app.bind_context` takes caller-owned recorder storage and an `app.Admission`;
  `app.release_context` takes an `app.Termination` carrying the middleware
  outcome, cancellation reason, status, transfer counters, and finish time. A
  nil recorder fails the bind rather than skipping the events.
- `app.request_recorder` exposes the live recorder to middleware and handlers,
  which is how an application labels an event it does not own.
- `observability.begin` takes the matched route name, so the start event is
  complete when it is emitted. `set_route` still renames a live event.
- `observability.init_recorder` prepares released storage for another request
  and keeps the sequence counting across a recorder's whole lifetime.
- `testing.init` no longer takes a recorder. The harness owns recorder storage
  and drives the ordinary application path, so its suites exercise the
  production event path.

## [0.6.0] - 2026-08-28

### Changed

- Pins `mach-http` v0.5.0, which carries the HTTP/3 connection engines and the
  rejected-request release fix. Laurel does not construct HTTP/3 connections, so
  that release's breaking storage change does not reach a Laurel consumer.

## [0.5.0] - 2026-08-28

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
