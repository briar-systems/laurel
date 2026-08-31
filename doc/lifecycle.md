# Application lifecycle

`lifecycle.Controller` is caller-owned state for a fixed sequence of service
callbacks. `app.App` drives the same controller for the production application
boundary, closing admission before drain and stop.

`start`, `poll_ready`, `drain`, and `stop` return the first lifecycle failure.
When a later `stop` callback also fails while cleanup is unwinding that primary
failure, `stop` continues to return the primary failure. The caller obtains the
separate cleanup result through `lifecycle.cleanup_failure` or
`app.cleanup_failure`.

Before a cleanup callback fails, either query returns a `TRANSITION_OK`
transition with no component and no error. Once cleanup fails, it returns
`TRANSITION_FAILED` with that callback's component and error. The query is
read-only, so observing cleanup does not change stop ownership or retry it.
