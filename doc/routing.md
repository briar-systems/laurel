# Routing

`laurel.router` is the typed application boundary over `http.router.router`. Mach HTTP remains the sole owner of method, authority, request-target, precedence, conflict, and percent-encoding semantics. Laurel adds handler ownership, declared parameter types, application errors, and request-scope allocation.

## Compilation

Each `Route` declares a typed `Method`, `Host`, `Path`, ordered parameter declarations, and one Laurel handler. Exact methods carry a validated `http.core.method.Method`. Host kinds are any, exact, or suffix. A suffix pattern uses the Mach HTTP `*.example.com` form. Path patterns use literal segments, `:parameter` segments, and one terminal `*wildcard` segment. `non_path()` selects authority-form or asterisk-form routing according to the request method.

`compile` consumes caller-owned `Storage` for matcher specifications, compiled routes, and segments. Routes, parameter declarations, and storage remain stable for the router lifetime. A router compiles exactly once. Replacement or hot reload uses a separately compiled router generation, so active requests never observe in-place route mutation.

Compilation proves that each parameter declaration matches the name, order, and wildcard role encoded by the path. Missing handlers, invalid typed method or host combinations, malformed and unreachable paths, declaration mismatches, capacity exhaustion, and semantic conflicts return a `Compile` result with exact route indices and a structured `AppError`. An application cannot assemble with an uncompiled router.

## Dispatch and decoding

`dispatch` first asks Mach HTTP to validate and match the request. A request with no parameters performs no allocation. Parameterized matches allocate bounded capture records, decoded bytes, and `context.Param` records only through the supplied request allocator. These allocations belong to the request scope and remain valid until that scope is released.

Built-in decoders cover decoded text, unsigned and signed 64-bit integers, booleans, and canonical UUID text. Integer decoding rejects signs outside the declared type and rejects overflow before arithmetic. Boolean decoding accepts only `true` and `false`. UUID decoding requires the 8-4-4-4-12 form. A custom `Decoder` receives the request allocator, a fully percent-decoded view, and isolated value output. It may allocate only through that allocator and must publish the declared value kind on success.

Malformed methods, authorities, targets, encoded separators, controls, dot segments, and invalid percent encoding return `DISPATCH_BAD_REQUEST` before parameter decoding. Decoder failures return `DISPATCH_PARAMETER_ERROR` with the decoder's exact `AppError`. Allocation, stale state, contract violations, and impossible matcher results return `DISPATCH_REJECTED`. No failed dispatch publishes parameters.

The successful flow is:

1. dispatch the HTTP request with its request-scope allocator
2. bind the returned `context.Params` to the exact exchange generation
3. invoke the matched handler through `invoke`
4. release the context and its request scope together

`invoke` rejects a changed router generation, request generation, handler, context, or parameter set. Dispatch results therefore cannot be replayed across requests or router generations.

## The routed terminal

A host ends its middleware chain in the dispatched route, and what a dispatch status means is the same wherever it is ended: `DISPATCH_MATCH` invokes the route, `DISPATCH_NOT_FOUND` runs the application's fallback, and `DISPATCH_BAD_REQUEST`, `DISPATCH_REJECTED` and `DISPATCH_PARAMETER_ERROR` return the dispatch's own `AppError`.

`terminal(routes, fallback, matched)` builds that mapping and `terminal_handler` gives it as a `handler.Handler` to pass to `app.execute`. The `Terminal` is caller-owned and lives as long as the request. A `Terminal` holding a status outside the five above, which is what a caller that never stored a dispatch has, returns an internal error naming that rather than a failure with no error in it.

A host that wrote this mapping itself would have to be changed when a status is added or when one of them starts carrying something extra, such as a 405 with `Allow`. Ending the chain through `terminal_handler` means it does not.
