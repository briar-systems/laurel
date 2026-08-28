# Middleware and error execution

Laurel executes one application-owned middleware stack for each bound request
context. The stack is validated during application assembly. Its maximum depth
and panic policy are fixed in the application configuration.

## Execution order

For middleware `A` and `B`, followed by terminal handler `H`, successful
delegation has this exact order:

1. `A` runs before `middleware.call`.
2. `B` runs before `middleware.call`.
3. `H` runs.
4. `B` resumes after `middleware.call`.
5. `A` resumes after `middleware.call`.

A middleware that returns without calling its `Next` token short-circuits the
rest of the stack. A terminal handler can return `handler.RESPOND` when it owns
the response or `handler.NEXT` when the surrounding application dispatcher may
continue. Any other action is an internal application error.

Each `Next` token is generation-bound to one active execution frame and may be
called exactly once. Copies share the same call count. A second call, a retained
token, a token used with another context, or a token used after its frame returns
is rejected as an internal error. The frame array is allocated from the request
allocator and dies with that request scope.

## Errors and cancellation

Errors unwind through middleware in normal return order. An outer middleware
may inspect or replace an error returned by an inner middleware or handler. Once
the stack has unwound, Laurel invokes the configured mapper exactly once while
the request context remains active.

Cancellation is checked before and after every middleware and terminal call.
Cancellation prevents deeper handlers from starting. It unwinds already active
middleware, returns `EXECUTION_CANCELLED`, and does not invoke the response
mapper after the request scope becomes inactive.

The default mapper uses canonical status codes. It emits only validated public
text and never reads `AppError.detail`. Internal errors always render the fixed
text `internal server error`, regardless of their supplied public message. The
mapper replaces only an uncommitted response with no live body owner. It clears
existing fields, emits bounded plain text with `cache-control: no-store`, and
allocates body state only from the request allocator.

## Panic policy

Mach panics terminate the process and do not provide recoverable unwinding.
Laurel therefore supports only `middleware.PANIC_ABORT`. Application assembly
rejects every other policy. A process supervisor must treat a panic as a failed
worker and replace it. Laurel never pretends that request state can be recovered
after a panic.

## Application boundary

Call `app.execute` only with a context admitted and bound by that same `App`.
The application verifies context ownership, uses its assembled middleware and
error mapper, and applies its configured depth and panic policy. An ownership
mismatch is returned without mutating or rendering into the foreign context.
