# Benchmark

A reusable harness that measures the same three-route service implemented three
ways, so that Laurel's runtime cost can be seen next to two mature stacks rather
than quoted on its own.

- **Laurel**, hosted by [hedge](https://github.com/briar-systems/hedge)
- **Go**, `net/http` with the standard library router
- **Rust**, `axum` pinned in `Cargo.toml`

Read [`COMPARISON.md`](COMPARISON.md) for what the numbers mean and what writing
each version is like. Measured results are in [`results/`](results/).

## The three routes

Identical in all three implementations, down to the response bytes.

| route | what it exercises | response |
|---|---|---|
| `GET /json` | a fixed body and the response path | `{"message":"hello"}` |
| `GET /echo/{id}` | a typed `u64` path parameter | `{"id":42}` |
| `POST /submit` | a bounded urlencoded form body | `{"name":"laurel"}` |

All three servers also set the same five security response headers, because
Laurel's security policy sets them and a comparison where one side does less
work is not a comparison.

## Running it

```sh
cd doc/bench
./run.sh          # 10 second cells, the published setting
./run.sh 2        # shorter, for checking the harness
```

It builds all three servers, starts each on its own loopback port, and writes
`results/<date>-<hostname>.md`.

`oha` v1.16.0 is fetched into a gitignored `.tool/` on first use. That release
publishes no musl build, so the harness uses the `oha-linux-amd64` asset.

Requirements: `mach`, `go`, `cargo`, `python3`, `curl`, and `gh` for the first
download.

## The matrix

Each cell is one server, one route, one connection count, run for the configured
duration.

- connections: 64 and 256
- duration: 10 seconds per cell
- five server variants: Laurel, Go and axum each restricted to one thread, plus
  Go and axum with every core available

Hedge's serve loop is single threaded, so the like-for-like table restricts the
baselines to one thread too: Go with `GOMAXPROCS=1`, axum on tokio's
current-thread runtime. The all-core table is reported separately, because a
reader choosing a stack needs to know the ceiling as well as the per-thread cost.

Every server is warmed for two seconds per route before its first measured cell.

## What is recorded

Requests per second, p50 and p99 come from `oha --output-format json`, parsed by
[`parse.py`](parse.py). Peak resident set is `VmHWM` from `/proc/<pid>/status`,
the highest the kernel ever saw, and CPU time is user plus system from
`/proc/<pid>/stat`, both read for the whole matrix per server.

Two failure counts are kept apart, because they mean different things:

- **non-2xx** is the server answering wrongly. Any cell with a non-zero count is
  listed under "Cell health" in the results, and its row cannot be read as a
  measurement of success.
- **transport errors** are connections dropped without a status. oha ends a run
  by abandoning whatever is in flight, which produces roughly one per
  connection, so only counts well above that are reported.

That distinction is worth keeping. The first run of this harness reported
Laurel at 14,419 requests/s on `GET /json` at 256 connections, higher than at 64
connections, which is the wrong shape. The cause was 48,231 transport errors:
the server's connection pool was sized to 256 while its configuration admitted
512, so a third of the load was being refused cheaply and the survivors looked
fast. Correcting the pool brought the figure to a consistent 10,015.

## Layout

| path | what it is |
|---|---|
| `run.sh` | builds, starts, measures, writes the report |
| `parse.py` | one oha JSON report to one result line |
| `report.py` | result lines to the results markdown |
| `laurel/` | the Laurel implementation, hosted through `hedge.service.laurel` |
| `go/` | the Go implementation |
| `axum/` | the Rust implementation |
| `results/` | committed measured results |

## Reading the results honestly

Every Laurel number is Laurel **and** hedge. The harness does not attribute the
difference between the framework and the server underneath it, and hedge's
HTTP/1.1 path is young. A separate in-process harness would be needed to say how
much of the gap belongs to which layer, and it does not exist yet.

The numbers are loopback request-path measurements on one machine, with the load
average recorded before and after each run. They are not a deployment
measurement and there is no TLS, HTTP/2 or HTTP/3 in them.
