# Laurel demo

A small but real Laurel application, hosted by hedge the way hedge's own
executable runs: a supervisor and several workers, each serving on a thread of
its own, all entering the one application. It has a JSON route, a route with a
typed path parameter, a route that decodes the query string, a route that reads
the raw request body, an HTML form protected by a CSRF token, a session cookie,
one middleware, and an observer. Beside the application, hedge serves a static
file and a health check from its own configuration. Every one of those uses the
real API of laurel and hedge. Nothing here is a mock.

## Run it

The demo is its own Mach project with its own dependencies, so it does not
inherit the repository's `dep/`. It needs mach 5.12.

```sh
cd demo
mach dep update . --all
mach build . --profile release
mach run . --profile release -- hedge.toml
```

`mach dep update` rather than `mach dep pull`, because hedge selects its own
dependencies by exact version and the demo commits no gitlinks for them, so they
are resolved rather than realized. `mach run` forwards everything after `--` to
the program, which is how the demo receives its configuration path, and a
second argument `--quiet` stops the per-request log. The first build takes a few
minutes and a few gigabytes of memory; after that only the third command is
needed.

The listen address comes from the environment, through
`address = "${ENV:LISTEN_ADDRESS}"` in `hedge.toml`. The demo's resolver reads
`LISTEN_ADDRESS` when it is set. A platform such as Railway sets only `PORT`, so
without `LISTEN_ADDRESS` the demo listens on `0.0.0.0:$PORT`, and with neither it
listens on `127.0.0.1:8080`. The host block answers every name
(`server_name = "*"`), since a deployment's public name is not known here, so
the demo runs unchanged behind a platform's router.

The server prints the bound address, the worker count, and then
`laurel-demo: ready`. It stops on SIGINT or SIGTERM, drains, stops the
application, and prints `laurel-demo: stopped`.

## What each route proves

Run these against the running server. The responses are what this demo actually
returned, not what it is supposed to return.

**A JSON route.** The handler owns its bytes and its media type; Laurel does not
serialize anything for you.

```sh
curl -s http://127.0.0.1:8080/api/hello
# {"message":"hello from laurel"}
```

**A typed path parameter.** `/api/echo/:id` declares a `u64` decoder. Decoding
happens during dispatch, before the handler runs, so the handler receives a
number and never sees the text.

```sh
curl -s http://127.0.0.1:8080/api/echo/42
# {"id":42}

curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/api/echo/abc
# 400
```

A value that does not fit a `u64` is refused the same way; the handler is never
entered.

**A session cookie.** The form page creates a session on first visit and counts
visits in it. The cookie is AEAD-protected and its contents are opaque to the
client.

```sh
curl -s -D headers.txt http://127.0.0.1:8080/form > page.html
grep -i '^set-cookie' headers.txt
# set-cookie: laurel_demo_session=TFMBAQ...; Path=/; Max-Age=3600; Secure; HttpOnly; SameSite=Lax

cookie=$(grep -i '^set-cookie:' headers.txt | sed 's/^[Ss]et-[Cc]ookie: //; s/;.*//')
curl -s -b "$cookie" http://127.0.0.1:8080/form | grep -o 'visits: [0-9]*'
# visits: 2
```

Laurel refuses a session cookie that is not `Secure` and `HttpOnly`, so the demo
cookie carries both. Browsers treat `http://localhost` as a trustworthy origin
and will store it; `curl` will not send a `Secure` cookie over plain HTTP, which
is why the lines above pass the cookie back explicitly with `-b`.

**A form POST with CSRF.** The form page issues a token bound to the session.
The POST parses a bounded urlencoded body, looks the token up, and verifies it
against the session it was issued for.

```sh
token=$(grep -o 'name="csrf_token" value="[^"]*"' page.html | sed 's/.*value="//; s/"//')
curl -s -b "$cookie" -X POST -d "name=laurel&csrf_token=$token" \
    http://127.0.0.1:8080/form
# <!doctype html><title>laurel demo</title><p>accepted: laurel</p>
```

Every way of getting it wrong is refused with 403:

```sh
curl -s -o /dev/null -w '%{http_code}\n' -b "$cookie" -X POST \
    -d 'name=x' http://127.0.0.1:8080/form                      # 403, no token
curl -s -o /dev/null -w '%{http_code}\n' -b "$cookie" -X POST \
    -d 'name=x&csrf_token=AAAA' http://127.0.0.1:8080/form      # 403, bad token
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
    -d "name=x&csrf_token=$token" http://127.0.0.1:8080/form    # 403, no session
```

**A query string.** `GET /api/search` decodes the query with `query.parse`, the
same urlencoded decoder a form body uses, into storage the handler owns. It reads
`q` with `form.find` and types `limit` with `form.typed` and the `u64` decoder
that types path parameters, so an absent `limit` takes the default and one that
is not a number is refused before anything is answered.

```sh
curl -s 'http://127.0.0.1:8080/api/search?q=hello+w%C3%B6rld%22%3C&limit=3'
# {"q":"hello wörld\"\u003c","limit":3}

curl -s 'http://127.0.0.1:8080/api/search?q=x'
# {"q":"x","limit":10}

curl -s -w ' %{http_code}\n' 'http://127.0.0.1:8080/api/search?q=x&limit=abc'
# invalid route parameter 400

curl -s -w ' %{http_code}\n' 'http://127.0.0.1:8080/api/search?q=a&&b'
# malformed query 400
```

**A raw body.** `POST /api/raw` reads the whole body with `raw.Body` as its
exact bytes, as a webhook handler does before it checks a signature, and answers
with them. The first read usually suspends, like the form's. The demo's limit is
4096 bytes: a body of exactly that fits, and one byte more is refused with 413.

```sh
head -c 3000 /dev/urandom > in.bin
curl -s -X POST --data-binary @in.bin -o out.bin http://127.0.0.1:8080/api/raw
cmp in.bin out.bin && echo identical
# identical

head -c 4097 /dev/urandom | curl -s -w ' %{http_code}\n' -X POST --data-binary @- \
    http://127.0.0.1:8080/api/raw
# request body is too large 413
```

A chunked body with no declared length reads the same way.

**A static file and a health check.** Both are hedge's own services, `static`
and `fixed`, configured in `hedge.toml` and served by the workers on the same
listener without entering the application.

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/static/index.html
# 200

curl -s http://127.0.0.1:8080/healthz
# ok
```

**An unmatched path.**

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/nope
# 404
```

**The middleware and the observer** are visible in the responses and the log.
Every response carries the security headers the middleware applies after the
handler returns:

```sh
curl -s -D - -o /dev/null http://127.0.0.1:8080/api/hello | grep -i 'x-frame\|content-security'
# content-security-policy: default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
# x-frame-options: DENY
```

The observer prints one line per completed request, naming the worker thread
that served it, and, for a failed one, the private detail that never reaches the
client:

```
demo: api.hello -> 200 on worker thread 140055119134704
demo: request failed: kind 3 status 403: the form carried no csrf_token field
```

**Several workers.** Every request is served by one of the four workers, and the
kernel spreads new connections across them. 200 requests, each on a connection
of its own, landed on all four:

```sh
for i in $(seq 1 200); do curl -s -o /dev/null http://127.0.0.1:8080/api/hello; done
# in the server's log, counted by thread:
#   60 140055110746096
#   43 140055119134704
#   56 140055127523312
#   41 140055138009072
```

## How a Laurel application is hosted

This is the part worth reading before writing your own.

**Laurel owns no listener, no socket, and no event loop.** It defines the
application layer above `mach-http`: routing, middleware, sessions, forms,
errors, rendering, and lifecycle. It never accepts a connection. Nothing in the
framework can serve traffic on its own, and there is no `laurel serve`.

**Hedge is the server.** [Hedge](https://github.com/briar-systems/hedge) accepts
connections, speaks HTTP/1.1, HTTP/2 and HTTP/3, terminates TLS, serves files,
proxies, and dispatches matched routes into a *service*. A Laurel application is
one service kind among several. Hedge ships `hedge.service.laurel`, an adapter
that binds an assembled `laurel.app.App` to hedge's service handler contract, and
its configuration has a matching service kind:

```toml
[service.app]
kind = "laurel"
application = "site"
```

`application = "site"` is a name, not a path. The executable registers the
assembled application under that name in a `hedge.service.Applications` registry
it owns, and hedge resolves the name against that registry when it builds each
worker's services.

**The embedder writes a `main`.** Hedge's own binary serves files and proxies but
registers no applications, because a Laurel application is Mach code that has to
be compiled in. So an application is deployed by building a binary that links
hedge and your application together. `src/bin/main.mach` is that binary. It is
hedge's own `src/bin/main.mach` with one application registered, and it is the
whole of what an embedder writes:

1. read the configuration, validate it into a `schema.Graph`, and seal it into a
   configuration generation
2. assemble the Laurel application against the message limits hedge will commit
   its responses under, start it, bind it with `hedge.service.laurel.make`, and
   register `bound_handler` under its configured name
3. pass the registry as `composition.Options.applications` to
   `composition.start_process`, with the worker count `hedge.spread.count` reads
   from `server.workers`
4. `supervisor.make`, `supervisor.attach_reloads` with a loader that seals the
   next generation, `supervisor.start`, then `supervisor.run` until a signal
   stops the process and `supervisor.stop`
5. drain and stop the application, after every worker that could enter it has
   stopped

The supervisor thread takes the signals, reloads the configuration on SIGHUP and
drives certificate renewal. Each worker serves on a thread of its own, with its
own listeners, io runtime, timers and buffer pool. On Linux every worker binds
its own socket with `SO_REUSEPORT` and the kernel spreads connections across
them. The static files and `/healthz` are hedge's own `static` and `fixed`
services, configured in `hedge.toml` and served by the workers without entering
the application. A reload rebuilds hedge's services from the new configuration
and resolves `application = "site"` against the same registry again, so the
running application serves the new generation unchanged.

## The threading contract

Every worker is handed the same registry, so **one application instance serves
every worker at once**. Its handlers, middleware and callbacks run on several
threads concurrently. This is what that means for each part of it.

**Per-request state belongs to one worker.** `hedge.service.laurel` keeps the
request's context, recorder, execution cursor and outcome in the request arena
of the worker serving it, and dispatch writes its route captures there too. A
request is entered, suspended and resumed only by the worker that admitted it.
Nothing per request is shared, and a handler's `slot` and the memory it takes
from `request_context.alloc` are private to its request.

**What Laurel shares is safe to share.** Everything the `app.App` holds is either
fixed at assembly or synchronized:

- admission (`max_active_requests`) is one atomic counter
- the router, the middleware stack, the error mapper, providers, the security
  headers and origin policies, the vocabulary and the CSRF protector are
  written only when they are initialized or released, and are read-only while
  requests run. Dispatch writes only its own locals and the request's captures.
- the session manager's state is atomic, and the in-memory session store, the
  nonce and replay guards, the session and CSRF key rings, and the CSRF ring
  registry each take their own mutex

**The lifecycle is not synchronized.** `app.start`, `app.poll_ready`,
`app.drain`, `app.stop` and `app.release` belong to one thread, the embedder's.
Start the application before `composition.start_process` and drain it only
after `supervisor.stop` has returned, as `main` does here, and never call them
from a handler.

**The application's own state is the application's to synchronize.** Laurel
calls whatever the application hands it (handlers, middleware, the observer,
entropy sources, a session store or codec, an authenticator, a renderer,
providers) from every worker at once, with the same `ctx` pointer and the same
`app_state`. Anything those reach and change must be atomic or locked. The
demo's request and observer counts are `std.sync.atomic` counters for exactly
this reason, and a store or cache of your own needs a lock of its own. A value
written only before `composition.start_process` and never after needs nothing.

### What hedge's adapter does for the application

`hedge.service.laurel` runs Laurel's router itself, so routes with typed and
wildcard parameters dispatch exactly as they would under any other host. It
enters the application at the request headers, before any body byte has been
read, which is why `POST /form` is written as a handler that can suspend: the
form parser polls the body, a pending read leaves the chain with its token
(`handler.suspend`), and hedge resumes only that step once the read settles.
Nothing that already ran runs again. An exchange that dies while a step is
suspended is abandoned, and every middleware exit half that is owed still runs.

The adapter keeps Laurel's per-request state (the context, the execution cursor
and the recorder) in the request arena, whose bound the application declares:
`register_application` takes it as its last argument, and this demo asks for
64 KiB. Hedge claims that memory in chunks as the request needs it and returns
it when the exchange settles, so an idle connection holds none of it.

Connections are not pooled up front. Hedge grows its connection storage with
what is actually connected, and `server.limits.max_connections` is an optional
policy cap rather than a storage size, so this demo leaves it unset. The one
ceiling the application owns is `app.Limits.max_active_requests`, past which
Laurel refuses admission.

## Layout

| path | what it is |
|---|---|
| `src/bin/main.mach` | the executable: configuration, registration, composition, supervisor |
| `src/app.mach` | the application: routes, middleware, sessions, CSRF, observer |
| `src/handlers.mach` | the six route handlers |
| `hedge.toml` | workers, listener, host, services, routes |
| `public/static/` | the static file |

## Versions

The demo builds against Laurel's working tree through `path = "../"`, so it
shows whether the Laurel in this checkout still hosts under hedge. Hedge depends
on Laurel too, and Mach resolves dependencies flat, so the path overrides the
Laurel release hedge selects and `hedge.service.laurel` is compiled against this
tree. A Laurel change that breaks the adapter fails this build until hedge
follows it.

Hedge is selected as `=0.11.0`, the release that adds the supervisor and
multiple workers. std `^8.2` and mach-http `^0.20` admit the exact v8.2.0 and
v0.20.0 hedge selects, and Laurel accepts both. Hedge brings mach-crypto
v0.22.0, mach-tls v0.12.0, mach-quic v0.20.0 and mach-acme v0.9.0 with it.
