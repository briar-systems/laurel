# Observability and in-process tests

Laurel reports what a request did and lets an application be driven end to end
without a socket. Both layers are bounded, caller-owned, and fail closed.

## Structured request events

One `observability.Recorder` covers one request. It emits exactly one start
event and exactly one terminal event. The terminal event is `error` when the
request failed with an `error.AppError`, and `finish` otherwise. A second start,
a second terminal, or any mutation after the terminal is refused with
`RECORD_STATE` rather than emitting a second event.

`observability.RequestEvent` carries the request identity, method, target, route
name, status, error kind, start time, duration, bytes in, bytes out, phase,
outcome, the request generation, a per-recorder sequence number, and the label
set. Outcome is one of `OUTCOME_PENDING`, `OUTCOME_COMPLETED`, `OUTCOME_FAILED`,
`OUTCOME_CANCELLED`, or `OUTCOME_TIMED_OUT`, so cancellation and timeout are
distinguishable from an ordinary finish without a separate callback.

`observability.observe_execution` maps one `middleware.Outcome` and the request
cancellation reason onto exactly one terminal event, and
`observability.observe_completion` takes the authoritative transfer counters from
one `http.core.exchange.Completion`. An integration therefore cannot report a
duration or byte count it did not measure.

Every text field is copied into the event, so an event stays valid after the
request context is released and never borrows request memory.

### Fixed cardinality and size

Label names come from a closed `observability.Vocabulary` registered once at
initialization. A name outside that vocabulary is refused with `RECORD_UNKNOWN`
and never appears in an event, so the label name set is fixed by construction.
Names are lowercase letters, digits, and underscore, at most
`MAX_LABEL_NAME_BYTES`, unique within the vocabulary, and at most `MAX_LABELS`
in total.

Each name declares its own value policy. A spec with `value_count` non-zero
declares the complete permitted value domain and any other value is refused with
`RECORD_VALUE`, which fixes that label's cardinality exactly. A spec with
`value_count` zero permits any value within `max_value_bytes`, which bounds size
but not cardinality; use it only for values that are already bounded by
something outside Laurel. Values must be printable and non-empty. Setting a name
that is already present replaces its value, so an event never carries more
labels than the vocabulary declares.

Field lengths are bounded by `observability.Policy` and by the module maxima:
`MAX_REQUEST_ID_BYTES`, `MAX_METHOD_BYTES`, `MAX_TARGET_BYTES`, and
`MAX_ROUTE_NAME_BYTES`. The request identity and method are always rejected
rather than shortened, because both are already bounded by the application. The
target and route name follow `Policy.truncation`: `TRUNCATE_REJECT` refuses the
event outright and emits nothing, while `TRUNCATE_ELIDE` keeps the bounded
prefix and sets `RequestEvent.truncated`, so a consumer never mistakes a prefix
for a complete value.

## The in-process harness

`testing.Harness` drives one assembled `app.App` with no socket, no runtime, and
no client. It owns one invocation at a time and every buffer it uses comes from
the caller through `testing.Storage`: response fields, response trailers,
informationals, the request arena, and the response capture buffer.
`testing.storage_valid` rejects any two of those ranges that overlap, so an
invocation cannot corrupt its own capture through aliasing.

One `testing.invoke` performs the sequence a server would:

1. create the request cancellation scope, with a deadline when one is given
2. build the request body reader over the caller's bytes
3. initialize the request, response, and exchange for one generation
4. make the request allocator over the caller's arena
5. dispatch the route, allocating parameters from that arena
6. admit and bind the request context through `app.bind_context`
7. begin the request event and record the matched route name
8. execute the application middleware with a terminal that calls
   `router.invoke`, the application fallback, or the dispatch error
9. commit the response, or settle cancellation when the scope is not active
10. read the response body to completion into the capture buffer
11. drain the request body and finish the exchange
12. record the transfer counters and the one terminal event
13. release the context, the recorder, and the scope

Admission is real: an application that has not reached readiness, or that is
draining, refuses the invocation with `INVOKE_REJECTED` and no event is emitted.

### Streaming bodies

`testing.Request.fragment` bounds how many bytes one request-body read returns,
and `testing.Request.suspend` makes every read suspend once with a token the
handler must settle through `body.complete_reader`. A handler that parses a body
therefore meets fragmentation and suspension in process, exactly as it would
behind a socket.

The response body is pulled the same way. A suspended read is completed and
retried, bounded by `max_body_polls`; a body that never becomes ready inside
that budget returns `INVOKE_PENDING` and the exchange is cancelled rather than
left open. A body larger than the capture buffer sets `Response.truncated` and
the remainder is drained rather than dropped silently.

### Suites across every HTTP version

`testing.Case` pairs one request with one `testing.Expectation` over invocation
status, response status, execution status, and error kind; a zero field is not
checked. `testing.run_suite` runs every case against every supplied
`message.Version` and reports the totals plus the first failing case and
version. Passing `version_h1(1, 0)`, `version_h1(1, 1)`, `version_h2()`, and
`version_h3()` runs a suite against every wire version the `mach-http`
dependency exposes.

The harness needs no HTTP client. It never opens a connection, so client
protocol selection, pooling, and retry are outside its path entirely.

### Reuse between invocations

`Result.response.fields` and `Result.response.body` point into harness storage
and stay valid only until the next invocation. Copy anything that must outlive
one request. The harness itself is reusable and holds no state between
invocations beyond its monotonic clock.
