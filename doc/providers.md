# Host providers

A laurel application does not own a process. Whatever runs it, `laurel.serve`
or a binding into another server, is the host, and the host supplies the
facilities an application needs beyond a request: background tasks,
configuration, secrets, and telemetry. laurel defines each facility as an
interface, and the application only ever codes against the interface, so the
same application runs unchanged under any host and under the in-process test
harness.

Each interface is a record of a `ctx: ptr` and function pointers, in the same
style as `observability.Observer` and `upload.Store`. A host hands them to the
application through the ordinary `provider.Set`, under a fixed key:

| facility | module | key | the set resolves to |
|---|---|---|---|
| background tasks | `laurel.task` | `task.key()` = `laurel.task` | `*task.Provider` |
| configuration | `laurel.config` | `config.key()` = `laurel.config` | `*config.Provider` |
| secrets | `laurel.secret` | `secret.key()` = `laurel.secret` | `*secret.Source` |
| telemetry | `laurel.observability` | `observability.telemetry_key()` = `laurel.telemetry` | `*observability.Telemetry` |

A host that supplies a facility registers it under its key, and the
application's `app.Limits.max_provider_key_bytes` must admit that key. An
application that finds no provider under a key is running on a host that does
not supply the facility, and fails or degrades by its own choice. `task.resolve`
resolves and validates the task provider in one call.

## Background tasks

`task.Provider` runs work on its own schedule next to request handling: a
periodic refresh, an on-demand rebuild a handler can fire, and a snapshot every
handler reads without waiting. Tasks are process-scoped. They are registered
once, outlive any configuration reload, and stop when the host drains.

### Registering

`task.register` takes a `task.Spec` and returns an opaque `task.Handle`:

- `name` is a printable identifier used in reports. The provider borrows it for
  the task's lifetime.
- `state` is the task's own state, and `step` is its function. `state` erases
  to `ptr`, so it cannot hold secret-typed data (see Secrets below).
- `period`, when set, runs the task that long after the provider first sees it,
  then that long after each run ends. A task with no period runs only when
  triggered. An application that wants an immediate first run triggers it.
- `run_timeout`, when set, bounds each run.
- `slots`, `slot_bytes` and `slot_count` are caller-owned snapshot storage:
  `slot_count` slots of `slot_bytes` each, between `task.MIN_SNAPSHOT_SLOTS` and
  `task.MAX_SNAPSHOT_SLOTS`. A task with `slot_count` 0 publishes nothing.

Registration is refused once drain has begun. A provider holds at most
`task.MAX_TASKS` tasks, and a host may hold fewer. These bounds are
compile-time constants.

### Steps

A run is a sequence of non-blocking steps. `step(state, run)` returns
`STEP_DONE` when the run is complete, `STEP_PENDING` to be stepped again, or an
error view that fails the run. A step never blocks, so one task cannot stall
another task, the host's signal handling, or requests.

`task.Run` is valid only during the step. It carries the run's cancellation
scope, its deadline, its cause (`CAUSE_PERIOD` or `CAUSE_TRIGGER`), a sequence
number, and the secret source the host resolves secrets through. The scope is
cancelled when the host begins draining and times out at the run deadline, so a
step that waits on I/O attaches to it the same way a handler attaches to its
request scope.

### Triggering

`task.trigger` is single-flight. It returns `STATUS_OK` when it queues a run,
and `STATUS_COALESCED` when a run is already queued, in which case that run
serves both callers. A trigger while a run is in flight queues one follow-up
run, so a change that arrives mid-run is never missed and at most one run is
ever in flight. Once drain begins, a trigger is refused with
`STATUS_DRAINING`.

### Snapshots

A run publishes with `task.draft`, writing into the returned slot, and then
`task.commit`, or with `task.publish` for bytes it already has. The committed
slot becomes the task's current snapshot. `task.discard` gives an uncommitted
slot back, and a run that ends with a draft open has it discarded.

`task.read` never waits on a run. It returns a `task.Lease` on the current
snapshot, or `STATUS_EMPTY` before the first publish. The lease counts as a
reference on its slot until `task.release`, and a counted slot is never
reused, so a handler reads a stable snapshot for as long as it holds the lease.

A publish needs a slot that is neither current, leased, nor already drafting.
When every slot is held, `task.draft` and `task.publish` return `STATUS_FULL`
and the current snapshot stays in place. A task that keeps serving its last good
snapshot on a failed refresh gets that behaviour for free.

### Drain and stop

Only the host calls `task.drain` and `task.stop`. The first `drain(deadline)`
cancels every running task's scope, refuses further triggers and
registrations, and drops queued runs that have not started. Running tasks keep
being stepped until they finish or the deadline passes. A run still in flight
at the deadline is abandoned: it is never stepped again, its report says
`OUTCOME_ABANDONED`, and `task.Drain.abandoned` counts it. `drain` returns
`DRAIN_PENDING` until no run is in flight and `DRAIN_DONE` after, and a repeated
call must pass the same deadline. The deadline is a monotonic `time.Instant`,
and a provider enforces it itself.

`task.stop` is refused with `STATUS_BUSY` until drain is done and every lease is
released. After it, every operation is refused.

`task.report` returns a task's run, failure, and abandonment counts, its last
outcome and error, whether a run is running or queued, and the sequence of its
current snapshot.

### The task runner

`laurel.task.runner.Runner` implements `task.Provider` in caller-owned
storage, and it is the one runner both hosts use. Nothing runs until
`runner.poll(runner, now)`, which takes the caller's clock, schedules due
periods, starts queued runs, steps each running task once, and abandons runs
still in flight past the drain deadline. Every provider call and `poll` take
the runner's lock, and a step runs with the lock released, so a step may
publish, read or trigger through the provider and handlers may read snapshots
from any thread. One driver polls at a time.

`laurel.testing` drives it by hand: a test calls `poll` with a fixed clock, so
a task runs exactly when the test says, with no thread and no clock.
`laurel.serve` drives it from a thread of its own, polling when the runner
reports work (`runner.next_due`, and `runner.on_wake` for a registration,
trigger or drain), and stepping a run that returned `STEP_PENDING` again after
`serve.Options.step_interval_ns`.

## Secrets

mach refuses to erase a pointer that can reach secret-typed (`^`) data to the
untyped `ptr`, and that refusal is transitive: it covers a record that holds a
secret, a record that points at one, and a record whose function pointer takes
one. Every provider interface above erases its context to `ptr`, so none of
them can carry a secret.

`secret.Resolver` is the one record that does. Its `borrow(ctx, name, use,
use_ctx)` hands the named secret to `use` as `contracts.SecretBytes`, valid for
that call only. The host copies the secret into scratch storage for the call and
zeroes it after. Because the resolver's own callback type mentions a secret,
the resolver cannot erase, so it is registered with `secret.register` into a
bounded module-private table (`secret.MAX_RESOLVERS` entries), and everything
else holds the public `secret.Source` it returns. This is the same arrangement
`security.csrf` uses for its key rings.

`secret.borrow(source, name, use, use_ctx)` resolves the source and borrows the
named secret. `secret.unregister` is refused while a borrow through the source
is in flight.

A task therefore holds only public names. The host owns the resolver, and each
`task.Run` carries its `secrets` source, so a periodic job that signs requests
with a token borrows the token in the step that needs it, and no secret ever
sits in task state.

## Configuration

`config.Provider.read(ctx, key, output, capacity)` copies the value for a key
into caller storage. It returns `READ_FOUND` with the length, `READ_MISSING`,
or `READ_TOO_LARGE` with the length needed. Keys are lowercase letters,
digits, `_`, `-` and `.` in non-empty dot-separated segments, at most
`config.MAX_KEY_BYTES` bytes. `config.read` validates the key and the
provider's answer, and turns an answer that claims more bytes than the caller
gave into `READ_INVALID`.

## Telemetry

Request events stay where they are: `app` drives the `observability.Observer`
for every admitted request (see [observability](observability.md)).
`observability.Telemetry` carries the signals an application produces outside
a request, such as a task's refresh count or the size of its last snapshot.

`observability.init_signal` builds a `SIGNAL_COUNTER` (a non-negative
increment), `SIGNAL_GAUGE` or `SIGNAL_EVENT` with a name and value.
`observability.signal_label` labels it from the application's existing
`observability.Vocabulary`, under the same rules as request labels, so signal
cardinality is as fixed as request cardinality. `observability.emit` hands the
signal to the host's `emit` callback.

## Built-in providers under `laurel.serve`

`serve.Host` owns one of each facility, and `serve.providers(host)` returns
them as one `provider.Provider` entry that owns all four keys:

| facility | built in | configured by |
|---|---|---|
| background tasks | a `task.runner.Runner` on its own thread, drained with the application and stopped after it | `Options.step_interval_ns` |
| configuration | the process environment: key `a.b-c` reads `<prefix>A_B_C` | `Options.config_prefix` |
| secrets | the process environment: name `token` reads `<prefix>TOKEN`, copied into welded scratch for the borrow and wiped after it, at most `serve.MAX_SECRET_BYTES` | `Options.secret_prefix` |
| telemetry | one line per signal on stderr, written with one call | `Options.telemetry` |

An application replaces any of them by listing its own provider for that key
before the host's entry in its `provider.Set`: `provider.resolve` answers with
the first provider that owns a key. `laurel.serve` drains and stops the task
provider the application's set resolves, whichever that is. An environment
secret sits in process memory in the clear for as long as the process runs, so
a deployment that keeps secrets in a vault or a credentials directory supplies
its own `secret.Resolver`.
