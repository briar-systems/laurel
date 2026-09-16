# Forms and uploads

Laurel decodes form bodies incrementally into caller-owned storage. The form,
multipart, upload, and HTTP body layers remain separate so each owner has one
bounded state machine and one explicit completion token.

No parser allocates memory, chooses a filesystem path, or owns a request body.
Applications provide every result array, byte arena, work buffer, upload store,
and HTTP read buffer.

## URL-encoded forms

`form.UrlEncoded` decodes `application/x-www-form-urlencoded` input across
arbitrary fragment boundaries. A percent escape can span three calls to
`form.feed_urlencoded`. `+` becomes a space. Names and values are validated as
strict UTF-8 only after their complete decoded byte sequences are available.

The five limits are independent.

- `max_bytes` bounds encoded request bytes.
- `max_fields` bounds published fields.
- `max_name_bytes` bounds one decoded name.
- `max_value_bytes` bounds one decoded value.
- `max_temporary_bytes` bounds all retained decoded bytes.

`form.finish_urlencoded` rejects incomplete percent escapes, empty trailing
separators, and incomplete fields. Any failure clears all published fields and
decoded bytes. `form.result` succeeds only after finalization.

`form.BodyParser` joins the decoder to one `http.core.body.Reader`. It preserves
the reader's pending token, settles rejection exactly once, and never presents
a partial form as a successful result.

A `form.PENDING` operation means the body is not there yet. A handler returns
`handler.suspend(operation.token)` and is entered again through its `resume`
callback once the host has done the I/O, where it calls `form.complete_body`
with the settled token and carries on. It never spins on the read, so a body
larger than any buffer costs no more than the parser's own storage. See
`doc/middleware.md` for the suspension contract.

## Multipart forms

`multipart.Parser` recognizes exact CRLF MIME boundaries across arbitrary input
fragments. It supports nested multipart bodies up to `MAX_NESTING`, quoted
parameters, UTF-8 `filename*` parameters, fields, empty files, and streamed
files. Preamble bytes are rejected. Epilogue bytes are ignored after the final
top-level boundary.

The multipart limits are independent.

- `max_total_bytes` bounds encoded body bytes.
- `max_parts` bounds all field, file, and container parts.
- `max_headers_per_part` bounds header count for one part.
- `max_header_bytes` bounds retained headers for one part.
- `max_field_bytes` bounds one decoded field value.
- `max_file_bytes` bounds one streamed file.
- `max_temporary_bytes` bounds retained names, values, metadata, and copied file
  identifiers.
- `max_nesting` bounds active multipart containers.

The caller supplies a `multipart.Storage` whose capacities satisfy the selected
limits. Parser state, upload state, parts, arena bytes, work bytes, provider
state, input fragments, and body-reader buffers must be physically disjoint.
Initialization rejects overlap before any parsing or provider operation.

`multipart.feed` reports exactly how many input bytes it consumed. When storage
returns pending work, the caller must retain the complete input range and keep
it immutable until `multipart.complete_pending` settles that token. A fresh
public token is issued for every pending provider turn. Stale tokens never reach
the provider.

`multipart.finish` is required after the body owner reports end of input. A
closing MIME boundary alone does not publish uploads. Finalization verifies the
top-level close and commits the request upload batch.

`multipart.BodyParser` joins parsing to one `http.core.body.Reader`. It can span
pending reads, pending upload operations, and pending body rejection without
losing which owner issued the token.

## Atomic upload batches

One `upload.Upload` represents one request-wide batch. Every file is staged
inside that batch. A file boundary seals only that file. It does not make any
file externally visible. `multipart.finish` asks the provider to publish every
staged file atomically after the complete body has been accepted.

The state sequence is:

```text
ready
  -> batch begin
  -> file begin -> write* -> file seal
  -> file begin -> write* -> file seal
  -> batch commit
  -> release
```

A malformed later part, limit failure, body failure, or cancellation takes the
batch abort path. The provider removes every staged file, including files sealed
before the failure. Laurel clears every logical part and result byte before it
returns the terminal failure.

The upload provider surface has seven operations.

| Callback | Required effect |
| --- | --- |
| `batch_begin` | Create an isolated unpublished staging namespace and return its transaction. |
| `file_begin` | Create one staged file inside the named batch and bind its metadata. |
| `write` | Consume a nonzero prefix of the supplied bytes for the named batch and file. |
| `file_seal` | Close one staged file and return its opaque identifier without publishing the batch. |
| `batch_commit` | Publish all sealed files atomically and exactly once. |
| `batch_abort` | Remove all staged files and the optional active file exactly once. |
| `complete` | Continue the one provider operation named by its provider token. |

`batch_commit` is legal only with at least one sealed file. `batch_abort` accepts
either an idle batch or a batch with one active file. File-begin failures and
write or seal failures leave the batch active so Laurel can execute its single
abort path.

Each successful batch or file begin returns a `Transaction` whose owner equals
`Store.ctx` and whose nonzero identifier is distinct from the other active
transaction. Transaction values are immutable capabilities for their active
operation sequence.

Each successful file seal returns a nonempty provider-owned `StoredFile.id` and
the exact number of bytes accepted by `write`. The identifier remains immutable
through the next call on that `Upload`. The multipart parser copies it into its
caller-owned arena before another provider call, so multipart results never
borrow provider memory.

## Provider ownership

`Store.context_size` declares the complete contiguous range beginning at
`Store.ctx`. `Store.aliases_state` reports any additional provider-owned ranges.
The ownership query is read-only. It cannot mutate the upload, parser, supplied
range, store descriptor, or completion state.

The `Store` descriptor is copied into `Upload` and remains fixed for the whole
session. Every callback is checked against a complete snapshot of upload state.
A callback that mutates Laurel-owned state poisons the batch and requires
external reconciliation.

Metadata views passed to `file_begin` point into `Upload` storage. They remain
immutable until synchronous return or final completion of that file-begin
operation. A write input remains borrowed and immutable until synchronous
return or final completion of that write. Providers cannot retain either range
after its operation settles.

One `Upload` permits one provider operation at a time. A `Store` can serve many
independent uploads concurrently. The provider owns any synchronization needed
for shared backing storage. Laurel never serializes unrelated requests through
global state.

## Pending work and cancellation

A pending `Progress` contains only its nonzero provider token, operation kind,
active outcome, and nil error. All other output fields are empty. A completion
can return another pending provider token. Laurel replaces the public token on
every turn while retaining the exact metadata or input ownership required by
the operation.

Cancellation waits for batch begin, file begin, write, or file seal to settle,
then aborts the batch. Cancellation cannot reverse a submitted batch commit.
Callers must settle that commit and use its outcome.

## Unknown outcomes

A provider reports `OUTCOME_UNKNOWN` only when it cannot prove whether a finish
operation took effect. Laurel then rejects release, retry, and further parsing.
The application must reconcile against durable provider state.

`upload.resolve_unknown` accepts `OUTCOME_COMMITTED` only for an uncertain batch
commit. It accepts `OUTCOME_ABORTED` for any poisoned batch after the provider
has removed or proven absence of all staged state.

`multipart.resolve_storage` applies the same resolution to a parser. A committed
resolution publishes the already validated caller-owned result. An aborted
resolution clears all parts and returns the original parser failure, or a
storage failure when no earlier parser failure exists.

No timeout or retry guesses an unknown outcome.
