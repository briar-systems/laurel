# Running standalone with `laurel.serve`

`laurel.serve` runs one laurel application on mach-http's HTTP/1.1 server
runner (`http.server.server`), with no other server in front of it but
whatever proxy terminates TLS. It is one host among several: the same
application runs in process under `laurel.testing`, and inside hedge through a
binding such as graft. The application never names its host.

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
thread. [`demo/standalone`](../demo/standalone) is a complete example.

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

## Current limits

- **No WebSockets.** The runner does not hand an upgraded connection to a
  handler yet (briar-systems/mach-http#191), so `realtime` WebSocket routes do
  not work under `laurel.serve`. Server-sent events and other streamed
  responses do, within the next limit.
- **Long streaming responses need a raised deadline.** The runner bounds a
  whole exchange, request and response, by `connection.request_timeout_ns`
  (briar-systems/mach-http#193), so a server-sent event stream or a slow
  download is cut off at it. Raise it for an application that streams.
- HTTP/1.1 only, plaintext. TLS, HTTP/2 and HTTP/3 are for a proxy in front, or
  for hosting inside hedge.
