# Running standalone with `laurel.serve`

`laurel.serve` runs one laurel application on mach-http's HTTP/1.1 server
runner (`http.server.server`), with no other server in front of it but
whatever proxy terminates TLS. It is one host among several: the same
application runs in process under `laurel.testing`, and inside hedge through a
binding such as [graft](https://github.com/briar-systems/graft). The
application never names its host.

## Running

```mach
var host: serve.Host;
serve.init(?host, serve.options_default());

# the application is assembled over the host's providers
my_app.assemble(?state, serve.providers(?host));

val report: serve.Report = serve.run(?host, ?state.application,
    serve.config_default(ip.endpoint(127, 0, 0, 1, 8080)));

app.release(?state.application);
serve.destroy(?host);
```

The host comes first because it owns the providers the application is
assembled over (see [providers](providers.md)). `run` takes an assembled
application that has not started, serves it on the calling thread until a
drain finishes, and returns once the server, the application and its tasks have
stopped. `serve.shutdown(host)` begins the same drain a signal does, from any
thread. [`demo/`](../demo) is a complete example.

`serve.Config` carries the server's own configuration (`server`, an
`http.server.server.Config`: address, connection and exchange bounds, buffer
memory, timeouts, and `drain_timeout_ns`), the size of each request's arena
(`request_arena_bytes`), whether signals drain it (`signals`), the allocator
for the server's records (nil for pages) and a `ready` callback with the bound
address.

## Lifecycle

The application's lifecycle runs through the server's hooks:

| server hook | laurel.serve |
|---|---|
| start | `app.start`, called again while it is pending |
| ready | `app.poll_ready`; the server accepts once the application is ready, then `Config.ready` is called |
| drain(deadline) | `app.drain` with the server's drain deadline, and `task.drain` on the application's task provider with the same deadline |
| stop | `app.stop`, then `task.stop` on the task provider |

A start that fails ends serving without the server's stop hook, so `run` stops
the application and its tasks itself, bounded by `stop_timeout_ns`. A failed
lifecycle transition is in `Report.lifecycle`, with `FAILURE_APPLICATION`.

## Signals and drain

With `Config.signals` set, `run` claims the process's signal source
(`std.process.events`) for its duration, and SIGTERM or SIGINT (a console close
or service stop on windows) begins the drain. The listener closes, requests
already read are answered, a response in flight keeps streaming, and idle
keep-alive connections close. The application's drain callbacks and the task
provider's drain run to the same deadline. At `drain_timeout_ns` what is still
in flight is abandoned: the handler step is abandoned, its middleware exit
halves run, and the request is released. `Report.server.abandoned_exchanges`
and `Report.tasks.abandoned` count what the deadline cut off.

## Requests

Each exchange's scratch holds laurel's request state and the request arena. A
request is routed, bound (`app.bind_context`), executed and, when a step
suspends on body I/O, resumed on the server's next turn for it. A step past the
application's `handler_timeout` is timed out through the exchange's scope when
the server wakes it at that deadline (`Call.wake_at`). The request is released
(`app.release_context`) when the server settles the exchange, after its
response is written, so the terminal request event carries the final transfer
and a drain waits for responses still on the wire. A request that arrives while
the application does not accept (draining, or at `max_active_requests`) is
answered 503.

Request identifiers are rendered by the host: 32 hex digits, the process start
time then a counter, cut to the application's `max_request_id_bytes`.

Each request's context carries a waker (`context.waker`) that wakes the
exchange on the server from any thread. A streamed response whose source
returned pending is pulled again once it is woken.

## Timeouts

The timeouts are the server's, in `Config.server`. A streamed response, such
as server-sent events or a slow download, is bounded by its progress, not by a
deadline over the whole exchange:

| field | bounds |
|---|---|
| `response_timeout_ns` | from the end of the request body to the response's first accepted write, and from each write the client accepts to the next (30s by default) |
| `tunnel_timeout_ns` | a WebSocket, from its handoff and from each read or write that moves bytes (60s by default) |
| `connection.request_timeout_ns` | an optional absolute cap over a whole exchange, off by default |

The request head, request body and idle keep-alive timeouts are as the server
documents them.

## WebSockets

A handler asks for a WebSocket with `realtime.upgrade` and responds (see
[output](output.md#sessions)). `run` negotiates and commits the 101 once the
middleware has run, or answers 400 when the handshake is invalid. Once the 101
is written and the request has settled, and laurel's terminal request event is
out, the server hands the connection to `run`'s tunnel owner, which pumps its
bytes through the session: what the client sent with the upgrade request first,
then each read, with each write the session queued. The request's scratch,
arena included, stays with the connection until the session ends, so the
session and anything else the handler allocated there live as long.
`TUNNEL_BUFFER_BYTES` for reads and again for writes are taken from that arena
at the handoff, so `request_arena_bytes` must leave room for them beside the
session. A connection upgraded without a session, or tunnelled with CONNECT, is
closed.

A drain signals `SIGNAL_DRAIN` to every open session, then closes it with 1001
unless it closed itself. A session whose peer answers the close ends cleanly. One
still open at `drain_timeout_ns` is cut, its end callback runs, and it is counted
in `Report.server.abandoned_tunnels`. `Report.server.tunnels` counts handoffs. A
session idle past `tunnel_timeout_ns` is cut too, so a quiet one needs a
heartbeat.

## Current limits

- HTTP/1.1 only, plaintext. TLS, HTTP/2 and HTTP/3 are for a proxy in front, or
  for hosting inside hedge through [graft](https://github.com/briar-systems/graft).
