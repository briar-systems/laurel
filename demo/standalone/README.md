# Standalone example

One laurel application run on its own by `laurel.serve`, with no other server.
[`src/app.mach`](src/app.mach) is the application, written against the
providers its host supplies, and [`src/bin/main.mach`](src/bin/main.mach) is
the whole of what hosting it takes: create the host, assemble the application
over the host's providers, and run. The same `assemble` runs in process under
`laurel.testing` in the test at the end of `src/app.mach`.

## Run it

The example is its own Mach project with its own dependencies.

```sh
cd demo/standalone
mach dep pull .
mach build . --profile release
PORT=8080 mach run . --profile release
```

`mach dep pull` realizes the pins committed under `dep/` and copies laurel from
this working tree. The server listens on `127.0.0.1:$PORT` (8080 without it),
prints the port once the application is ready, and on SIGTERM or SIGINT drains,
stops the application and its task, and prints what it served.

`mach test .` runs the in-process test.

## What it serves

- `GET /hello` answers a fixed text body.
- `GET /greeting` answers the `greeting` configuration value, which the
  built-in provider reads from `STANDALONE_GREETING`, or `hello` without it.
- `GET /refreshes` answers the count a background task publishes: it runs once
  at start and every five seconds after, on the host's task thread, and each
  run emits a `refreshes` counter on stderr through the built-in telemetry.
  The handler reads the latest snapshot and never waits on a run.
- `POST /echo` answers the request body, up to 4096 bytes, reading it as it
  arrives and suspending on the host until it has.

```sh
STANDALONE_GREETING=hi PORT=8080 mach run . --profile release &
curl localhost:8080/hello
curl localhost:8080/greeting
curl localhost:8080/refreshes
curl --data-binary 'some bytes' localhost:8080/echo
kill -TERM %1
```

See [`doc/serve.md`](../../doc/serve.md) for the hosting contract and its
current limits, and [`doc/providers.md`](../../doc/providers.md) for the
providers.
