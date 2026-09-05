# Laurel against Go and axum

Three implementations of the same three-route service, measured on one machine.
This document says what the numbers mean and what writing each one is like. The
measured tables live in [`results/`](results/); the numbers quoted here are from
[`results/2026-09-05-D00.md`](results/2026-09-05-D00.md).

The three sources:

| | file | lines |
|---|---|---:|
| Laurel | [`laurel/src/handlers.mach`](laurel/src/handlers.mach) + [`laurel/src/app.mach`](laurel/src/app.mach) | 511 |
| Laurel, hosting | [`laurel/src/host.mach`](laurel/src/host.mach) + [`laurel/src/bin/main.mach`](laurel/src/bin/main.mach) | 742 |
| Go | [`go/main.go`](go/main.go) | 114 |
| Rust | [`axum/src/main.rs`](axum/src/main.rs) | 135 |

## Performance

Hedge serves from one thread, so the comparison that means anything is one
thread against one thread. `GET /json` at 256 connections:

| | requests/s | p50 ms | p99 ms |
|---|---:|---:|---:|
| Laurel + hedge | 10,015 | 22.271 | 23.833 |
| Go `net/http`, `GOMAXPROCS=1` | 47,356 | 5.379 | 10.312 |
| axum, tokio current_thread | 91,440 | 2.769 | 3.327 |

**Laurel is about 4.7x slower than single-threaded Go and 9.1x slower than
single-threaded axum on the cheapest possible route.** That gap is the headline
and it is not close. The shape holds across all three routes and both connection
counts, and it widens on the form POST, where Laurel reaches 6,097 requests/s
against axum's 83,206.

Latency follows throughput: Laurel's p50 at 256 connections is 22-30 ms where
axum is under 3.2 ms. Laurel's p99 stays close to its p50 on the two GET routes,
which says the loop is saturated but fair rather than erratic. The exception is
the form POST, where p99 reaches 125 ms against a 30 ms p50: that route pays an
extra scheduling round trip, described below.

Against the baselines with every core available the distance is much larger,
because there is nothing on the Laurel side to widen. axum reaches 348,198
requests/s and Go 221,305 on the same route. A reader deciding between these
stacks should read that as the real ceiling difference, not the single-thread
table.

Memory is the one place Laurel is competitive but not winning:

| | peak RSS |
|---|---:|
| Laurel + hedge | 35.9 MiB |
| Go, one thread | 18.1 MiB |
| axum, one thread | 10.6 MiB |

Laurel's footprint is dominated by preallocation rather than by garbage. Hedge
holds a fixed pool of 512 connection records with a 12 KiB arena each, and this
host preallocates one 8232-byte request state per pool slot. That is paid at
startup whether or not any traffic arrives, and it does not grow under load,
which is the property the design is aiming at. It is still three times axum.

The binary is the other cost: 13.9 MB for Laurel and hedge, 8.7 MB for Go,
1.0 MB for the Rust build.

### Where the time goes, honestly

This benchmark does not attribute the gap between the framework and the server.
Every Laurel number here is Laurel *and* hedge, and hedge is a young HTTP server
whose HTTP/1.1 path has not been optimised. A reader should not conclude that
the 4.7x is Laurel's routing and rendering; a large part of it may be the
connection engine underneath. Separating them needs a second harness that drives
the framework in process, which does not exist yet.

Two costs are clearly the framework's, though, and both are visible above:

- Every response body is copied. `render.init_fixed` takes a view of bytes the
  handler owns and the host copies them out through a `body.Reader` callback per
  chunk. Go and axum write the caller's bytes to the socket directly.
- Every admitted request runs the observer, the recorder, the middleware
  snapshot, and the admission accounting, whether or not the application uses
  any of them. None of those can be compiled out.

## Ergonomics

### The line count is not the whole story, but it is a real number

The application itself is 511 lines against Go's 114 and Rust's 135, for
identical behaviour. Roughly 4.5x. Where does it go?

**Nothing is inferred.** A route in axum is one line:

```rust
.route("/echo/:id", get(handle_echo))
```

and the handler signature `Path(id): Path<u64>` *is* the parameter decoder. The
Laurel equivalent declares the parameter, the decoder, the route, and the
storage the router compiles into:

```mach
bench.parameters[0] = router.Parameter{name: handlers.text("id"),
    wildcard: false, decoder: router.u64_decoder()};
bench.routes[1] = route(
    router.exact_method(method.from_kind(method.GET)),
    handlers.text("/echo/:id"), "echo",
    ?bench.parameters[0], 1, handlers.echo, (?bench.state)::ptr);
```

plus a `Storage` record naming three caller-owned arrays. The compiler then
checks that the declared parameters match the pattern, which is a real safety
property the other two do not have at compile time. It is also five times the
text.

**Nothing is allocated for you.** Writing a JSON body in Go is
`fmt.Sprintf` and `w.Write`. In Laurel the handler takes a buffer from the
request arena, writes digits into it by hand, and installs a `render.Fixed` over
it:

```mach
val allocated: R.Result[*u8, *u8] = A.allocate[u8](arena, room);
var length: usize = copy_in(out, room, 0, text("{\"id\":"));
val digits: usize = write_u64(found.unsigned_value, ?out[length], room - length);
```

There is no formatter, no string type that grows, and no JSON encoder. The
`write_u64` helper in `handlers.mach` exists because the framework does not
render a number. That is 22 lines of the file.

**Every component is mandatory and explicit.** A Laurel application cannot be
assembled without a router, a middleware stack, a provider set, a lifecycle
controller with at least one service, a security headers policy, an error
mapper, an observer, and an observability vocabulary. The benchmark uses none of
the provider set and does nothing in its lifecycle service, but both must exist
and be valid or `app.assemble` refuses. That is most of `app.mach`.

### What the framework refuses to do for you

These are deliberate, documented, and they are the reason the line count is what
it is.

- **No template engine and no serializer.** `render` converts bytes and sets a
  content type. `Renderer` is a contract with no provider in the framework.
- **No entropy source.** Sessions and CSRF both require the application to
  supply a fill function and a context that can report whether a byte range
  aliases its own storage. There is no default, on purpose.
- **No form field lookup.** `form` decodes into a bounded array in wire order.
  There is no `form.get`; the comparison loop is the application's.
- **No implicit response.** A handler that returns without installing a
  response is a distinct outcome, not an empty 200.
- **No global state.** No registry, no ambient allocator, no request-local
  storage the framework reaches into.

### Where Laurel is genuinely better

**Failure is typed and total.** Every fallible call returns a status or a
`Result`, and the compiler will not let it be ignored. `error.AppError` carries
a public message and a private detail as separate fields, and the default mapper
*cannot* leak the private one: an `INTERNAL` error's public text is replaced with
a canned string before it reaches the wire. Getting that wrong in Go or axum is
a code review question; here it is a type.

**Ownership is stated, not assumed.** The response body buffer must outlive the
exchange, and the framework says so and checks generations to enforce it. The
CSRF key ring is secret-typed, and the compiler refuses to erase a pointer to it
through an untyped context. That last one is not a nicety: it changed the shape
of this program. The key ring had to move out of the boot record and be owned by
`main` behind a typed pointer, because a secret cannot sit inside a struct that
is handed to a callback as `ptr`. Neither baseline has any equivalent.

**Bounds are declared up front.** Field counts, byte budgets, route parameters,
concurrent requests, and middleware depth are all configured numbers checked at
assembly. There is no input that makes this program allocate more than it
declared. Both baselines will happily grow a map.

### Where Laurel is genuinely worse

- **It is 4.7x to 9.1x slower per thread**, and single-threaded against
  multi-threaded baselines the practical gap is 20x to 35x.
- **It is 4.5x more code** for the same three routes, before counting the 742
  lines of hosting.
- **The hosting story is not finished.** Hedge's own Laurel adapter cannot use
  Laurel's typed router, because it admits requests with an empty parameter set
  and never runs dispatch. This benchmark supplies its own service handler to get
  around that. See [`../../demo/README.md`](../../demo/README.md).
- **A handler cannot wait for a request body.** Laurel handlers are synchronous,
  and hedge only reads sockets inside the poll that is running the handler, so
  the host must buffer the whole body before entering the framework. That costs
  an extra scheduling round trip per POST and is why `POST /submit` has the worst
  p99 in the table.
- **The per-request budget is tight.** Hedge gives a call a 12 KiB arena.
  Laurel's per-request state is 8232 bytes of it. This host keeps that state
  outside the arena so the application has room for a session, a form decoder,
  and a response body; without that move the form route runs out of arena and
  fails.
- **Type safety stops at the framework boundary.** Handlers are
  `fun(ptr, *context.Context)`, and the application state arrives as an untyped
  pointer that every handler casts. axum's extractors and Go's closures both
  keep that typed.

## What this benchmark does not measure

- TLS, HTTP/2 and HTTP/3, all of which hedge supports and none of which are
  exercised here.
- Anything over a network. Every request is loopback, so the numbers are a
  request-path measurement, not a deployment measurement.
- Concurrency across cores for Laurel, because hedge serves from one thread.
- Sessions and CSRF under load. The benchmark application deliberately has
  neither, so that all three programs do the same work. The demo has both.
- The framework alone. Every Laurel number includes hedge.
