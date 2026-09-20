# Laurel demo

A small but real Laurel application, served over HTTP on a local port. It has a
JSON route, a route with a typed path parameter, an HTML form protected by a
CSRF token, a session cookie, a static file, one middleware, and an observer.
Every one of those uses the framework's real API. Nothing here is a mock.

## Run it

The demo is its own Mach project with its own pinned dependencies, so it does
not inherit the repository's `dep/`.

```sh
cd demo
mach dep pull .
mach build . --profile release
mach run . --profile release -- hedge.toml
```

`mach run` forwards everything after `--` to the program, which is how the demo
receives its configuration path. The first build takes a few minutes and a few
gigabytes of memory; after that only the third command is needed. The server
prints the bound address and then `laurel-demo: ready`, and serves on
`127.0.0.1:8080`.

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

**A static file.** Served by the server, not the application, on the same
listener.

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/static/index.html
# 200
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

The observer prints one line per completed request and, for a failed one, the
private detail that never reaches the client:

```
demo: request failed: kind 3 status 403: the form carried no csrf_token field
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
assembled application under that name with `hedge.service.register_application`,
and the dispatch plan resolves the name to a handler when it compiles.

**The embedder writes a `main`.** Hedge's own binary serves files and proxies but
registers no applications, because a Laurel application is Mach code that has to
be compiled in. So an application is deployed by building a binary that links
hedge and your application together. `src/bin/main.mach` is that binary and is
the whole of what an embedder writes:

1. read the configuration and validate it into a `schema.Graph`
2. seal a configuration generation, and inside that hook assemble the Laurel
   application, start it, and register it under its configured name
3. compile the dispatch plan against a resolver holding that registration
4. `serve.make`, `serve.start`, then drive `serve.poll` until it drains

Hedge is driven, not threaded. Every accepted connection, every parsed request,
and every Laurel handler call happens inside `serve.poll` on one thread.

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
| `src/bin/main.mach` | the executable: configuration, registration, serve loop |
| `src/app.mach` | the application: routes, middleware, sessions, CSRF, observer |
| `src/handlers.mach` | the four route handlers |
| `hedge.toml` | listener, host, services, routes |
| `public/static/` | the static file |

## Versions

The demo pins Laurel `v0.14.0` and hedge `v0.6.0`. It pins the Laurel *tag*
rather than resolving the working tree it lives in, because hedge depends on
Laurel too and Mach resolves dependencies flat: one revision of Laurel serves
the whole build, and `hedge.service.laurel` is compiled against it. Resolved by
path, a breaking change to Laurel would break hedge's adapter in the same pull
request, and that request could never merge until hedge had followed a release
that could not yet exist. The tag pin is what lets Laurel change first.
