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

`Next` is passed by value. Each token carries the request generation, execution
identity, context identity, and snapshot index. It never points at an execution
frame. Copies share one call state through the active request context. A second
call, a retained token, a token used with another context, or a token used after
its callback returns is rejected as an internal error before Laurel accesses
execution storage.

A token may be copied only to invoke it during its callback. It must not be used
after `middleware.execute` returns. Calling any Laurel API through a retained
token after the caller has destroyed the `context.Context` storage is invalid
because the context itself is caller-owned. While that context remains alive,
retained-token rejection is deterministic and never dereferences stack-dead
execution state.

At execution entry Laurel captures the stack pointer and length, allocates a
request-scoped snapshot, and copies each middleware callback into that snapshot.
Growing, shrinking, or replacing the application `Stack` during a callback does
not change the active chain. Concurrent mutation while the initial snapshot is
being copied is not supported and must be excluded by the application owner.

One context can own only one execution at a time, including error mapping.
Reentrant execution with the same context fails without invoking the mapper.
The claim is released on every return path, so the same bound context may be
executed sequentially. A context cannot be unbound while it owns an execution.

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

## Application boundary

Call `app.execute` only with a context admitted and bound by that same `App`.
The application verifies context ownership, uses its assembled middleware and
error mapper, and applies its configured depth and panic policy. An ownership
mismatch is returned without mutating or rendering into the foreign context.
