# Middleware and error execution

Laurel executes one application-owned middleware stack for each bound request
context. The stack is validated during application assembly. Its maximum depth
and panic policy are fixed in the application configuration.

## The step contract

A middleware is two halves and a resume. A terminal handler is one half and a
resume.

`EnterFun`, `ResumeFun`, `Disposition` and `Result` live in `laurel.handler`;
`LeaveFun` and `Middleware` live in `laurel.middleware`.

```mach
pub def EnterFun:  fun(ptr, *context.Context, *ptr) handler.Result;
pub def ResumeFun: fun(ptr, *context.Context, ptr, handler.Settlement, u64)
    handler.Result;
pub def LeaveFun:  fun(ptr, *context.Context, ptr, handler.Result)
    handler.Result;

pub rec Middleware { ctx: ptr; before: EnterFun; resume: ResumeFun;
    after: LeaveFun; }
pub rec Handler    { ctx: ptr; call: EnterFun; resume: ResumeFun; }
```

Every step returns a `handler.Result`, which is either an `error.AppError` or a
`handler.Disposition`: `RESPOND` when the response is owned, `NEXT` when the
chain may continue, or `PENDING` with the body token the step is waiting on.
Build them with `handler.respond`, `handler.proceed`, `handler.suspend` and
`handler.fail` rather than by hand.

`EnterFun`'s third argument is an out slot. A step that needs anything on the
way out, or on resume, allocates it from the request allocator and writes the
pointer there. The driver holds that pointer for the life of the execution and
hands it back to `after` and to `resume`. A step's `ctx` is shared by every
concurrent request, so nothing per-request belongs in it. `after` and `resume`
may both be `nil` on a step that needs neither.

## Execution order

For middleware `A` and `B`, followed by terminal handler `H`, the order is:

1. `A.before` runs.
2. `B.before` runs.
3. `H.call` runs.
4. `B.after` runs.
5. `A.after` runs.

**`after` runs exactly once for every `before` that ran.** That includes the
step whose `before` short-circuited with `RESPOND`, a chain cut short by an
error, a cancelled request, and a request abandoned while suspended. Whatever
`before` acquires, `after` releases, and that pairing is the only ownership rule
a middleware has to hold.

A `before` that returns `RESPOND` stops the descent: no deeper step runs, the
terminal does not run, and the exit halves run from that step outward. An
`after` returns the result that keeps travelling outward, which is usually the
one it was handed.

At execution entry Laurel captures the stack pointer and length, allocates a
request-scoped snapshot, and copies each middleware into that snapshot. Growing,
shrinking, or replacing the application `Stack` during a callback does not change
the active chain. Concurrent mutation while the initial snapshot is being copied
is not supported and must be excluded by the application owner.

One context can own only one execution at a time, including error mapping.
Reentrant execution with the same context fails without invoking the mapper. The
claim is held from `app.execute` until a terminal outcome, across every
suspension, and a context cannot be unbound while it owns one.

## Suspension and resumption

A handler that meets `form.PENDING`, `multipart` pending, or a pending
`body.Progress` returns `handler.suspend(token)` instead of spinning on the
read. The pending disposition travels out through the chain to `app.execute`,
which returns `EXECUTION_PENDING` with `outcome.token`.

The execution record is host-owned storage:

```mach
pub fun execute(app: *App, execution: *middleware.Execution,
    terminal: handler.Handler, request_context: *context.Context)
    middleware.Outcome;
pub fun resume(app: *App, execution: *middleware.Execution,
    request_context: *context.Context) middleware.Outcome;
pub fun abandon(app: *App, execution: *middleware.Execution,
    request_context: *context.Context) middleware.Outcome;
```

A host keeps one `middleware.Execution` per exchange, next to the context and
the recorder, for as long as the request lives. The loop is: call `execute`; on
`EXECUTION_PENDING`, do the I/O the token names and call `resume`; repeat until
any other status.

`resume` enters the suspended step, and only that step, through its `resume`
callback with `SETTLE_READY`. Nothing that already ran runs again, however many
times the handler suspends. The step reads its own state back from the slot
pointer it was handed, and it is the step, not the host, that settles the body
token it was waiting on.

When the request is going away — the connection died, the host is shutting down,
the scope was cancelled — the host calls `abandon`. The suspended step is
entered once with `SETTLE_ABANDONED`, which asks it to release rather than to
work; it must not suspend again. Every `after` that is owed then runs with a
cancellation error travelling outward, and the outcome is `EXECUTION_CANCELLED`.
`abandon` also cancels the request scope, so every observer of the request
describes the same thing. `resume` on a scope that has already died does exactly
this too, so a host may always call `resume` and get the right behaviour.

Calling one of the two is mandatory. `EXECUTION_PENDING` is not a termination:
`observability.observe_execution` refuses it, and `context.unbind` refuses while
an execution is claimed, so a host that drops a suspended request without
abandoning it gets `app.release_context == false` and one `OUTCOME_UNREPORTED`
terminal event rather than a silent leak. A step's state lives in the request
arena the host owns, so its memory goes with the arena, but anything a `before`
acquired outside that arena is released by its `after`, and its `after` only
runs because the host called `resume` or `abandon`.

A step that never suspends pays nothing for any of this: it writes `nil` to its
state slot, leaves `resume` nil, and never sees a settlement.

## Errors and cancellation

Errors unwind through middleware in normal return order. An outer middleware
may inspect or replace an error returned by an inner middleware or handler. Once
the stack has unwound, Laurel invokes the configured mapper exactly once while
the request context remains active.

Cancellation is classified before input validation and before and after every
middleware and terminal call. A context that is already cancelled or timed out
returns `EXECUTION_CANCELLED` without invoking middleware, the terminal handler,
or the response mapper. Cancellation during a chain prevents deeper handlers
from starting, unwinds active middleware, and does not invoke the mapper after
the request scope becomes inactive.

`AppError` owns up to `error.MAX_PUBLIC_BYTES` public bytes and
`error.MAX_DETAIL_BYTES` private bytes inline. `Outcome` therefore remains valid
after the handler and mapper return. Construct errors with `error.make` or
`error.make_view`. Read their text through `error.public_text` and
`error.private_detail`. Input beyond either bound is rejected rather than
truncated. Mapper failures likewise own up to `error.MAX_RENDER_ERROR_BYTES`
through `error.RenderFailure`. Custom mappers construct failures with
`error.render_failure` or `error.render_failure_from_view` and read them with
`error.render_failure_view`.

Always build both through those constructors, never through a record literal.
Holding their bytes inline means both types contain arrays, and an array field
cannot be named in a record literal, so there is no correct literal form to
write — `error.AppError{}` is the only one that compiles and it is exactly the
construct briar-systems/mach#3108 calls unreliable. The constructors clear their
byte arrays explicitly for that reason. `error.no_error` is the zero-valued
failure for an outcome that carries an `AppError` slot it does not use.

This is one case of a rule that holds across the framework. A record literal
leaves every field it does not name holding the previous stack frame's contents,
not zero, so a literal must name every field of its record. A record containing
an array cannot satisfy that, because an array field cannot be named in a
literal at all, so those are built the other way: declare `var value: T;`, which
does zero the whole record including its arrays, then assign each field.
`error.AppError`, `error.RenderFailure`, `csrf.KeyGeneration`, and
`session.KeyGeneration` are the types that force the second form.

Nothing enforces this automatically. Enumerating the violations was a
workaround for briar-systems/mach#3108, and that defect is being fixed in the
compiler, so the constructors named above are what keep the rule.

The default mapper uses canonical status codes. It emits public text only when
it is nonempty, within the configured bound, valid RFC 3629 UTF-8, and contains
no C0, DEL, or C1 control code point. It never reads private detail. Internal
errors always render the fixed text `internal server error`, regardless of their
supplied public message. The mapper replaces only an uncommitted response with
no live body owner. It clears existing fields, emits bounded plain text with
`cache-control: no-store`, and allocates body state only from the request
allocator.

Context binding requires non-null allocate, reallocate, and deallocate
callbacks. Middleware and the default mapper revalidate those callbacks at each
allocating boundary. An allocator mutated into an invalid state fails closed
without invoking another callback. After every allocator callback, the default
mapper revalidates cancellation, response identity and generation, status,
commit and body ownership, and exact field and trailer storage. It initializes
the error response only after the final revalidation. A callback that commits,
installs a live body, changes field storage or response identity, advances the
generation, or cancels the request keeps that mutation and causes mapping to
fail without replacement.

## Panic policy

Mach panics terminate the process and do not provide recoverable unwinding.
Laurel therefore supports only `middleware.PANIC_ABORT`. Application assembly
rejects every other policy. A process supervisor must treat a panic as a failed
worker and replace it. Laurel never pretends that request state can be recovered
after a panic.

## Migrating from the `Next` contract

Before 0.11.0 a middleware was one callback that received a `Next` token and
called `middleware.call` in the middle of itself. `middleware.Next`,
`middleware.MiddlewareFun` and `middleware.call` are gone, and so is the whole
class of errors around them: a token cannot be retained, reused, or invoked
twice, because there is no token.

- Split each middleware at its `middleware.call`. What ran before it becomes
  `before`; what ran after it becomes `after`.
- Every local the old after-half read across the call becomes per-request state:
  allocate it in `before`, write it to the out slot, read it back in `after`.
- `ret middleware.call(next, ctx)` with nothing after it becomes a `before` that
  returns `handler.proceed()` and a nil `after`.
- A handler's `res[u8, error.AppError]` becomes `handler.Result`. Replace
  `res[...].ok{handler.RESPOND}` with `handler.respond()` and `res[...].err{e}`
  with `handler.fail(e)`. Handlers take a third `state: *ptr` argument and may
  write `nil` to it.
- `handler.Handler` and `router.Route` handlers gain a `resume` field, which is
  `nil` for a handler that never suspends.
- `app.execute` takes a `*middleware.Execution` the host owns per exchange. A
  host that returns a pending outcome must later call `app.resume` or
  `app.abandon`.

## Application boundary

Call `app.execute` only with a context admitted and bound by that same `App`.
The application verifies context ownership, uses its assembled middleware and
error mapper, and applies its configured depth and panic policy. An ownership
mismatch is returned without mutating or rendering into the foreign context.
