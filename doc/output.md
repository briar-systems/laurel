# Rendering and realtime responses

Laurel converts application values into response bytes without owning a
template language, a socket, or an allocator. `render` produces bounded bodies.
`realtime` produces streams, server-sent events, and WebSocket frames. Both
layers write into caller-owned storage and surface a full consumer as
backpressure rather than as growth.

## Rendering

`render.Renderer` is an application-supplied callback. Laurel never requires it,
never parses a template, and never chooses a body representation. A handler that
writes bytes itself uses the same body primitives the renderer would.

Two body sources exist and both are `http.core.body.Reader` implementations over
caller storage.

- `render.Fixed` publishes one immutable byte range with a declared length. Its
  reads are chunked by the configured `response_body` limits.
- `render.Stream` pulls from a `render.Source` and declares no length. The
  source returns `SOURCE_DATA`, `SOURCE_END`, `SOURCE_PENDING`, or
  `SOURCE_FAILED`. A pending chunk names a nonzero token, and the body owner
  settles it through `body.complete_reader`. The output pointer and capacity
  supplied to the suspended read are retained until that token settles.

`render.init_fixed` and `render.init_stream` reject any body that cannot fit the
configured chunk and chunk-count limits, so a body never becomes unrepresentable
after the response is installed. Fixed and stream readers should be initialized
under the host limits retrieved via `context.limits(request_context)` so that
reader limits fit within the exchange limits checked at commit time.

Cancellation reaches a stream through the body reader's cancellation scope.
`body.read` classifies the scope before it consults the source, so a cancelled or
timed-out request settles the source with `body.CANCEL` or `body.TIMEOUT` and
never asks it for another chunk.

### Content type and charset

`render.Media` holds one serialized `content-type` value. The media type must be
`token "/" token` and the charset must be a single token, both bounded by
`MAX_MEDIA_TYPE_BYTES` and `MAX_CHARSET_BYTES`. There is no implicit charset: a
`Media` built without one emits no `charset` parameter. `render.text_plain`,
`render.text_html`, and `render.application_json` are the explicit UTF-8 forms.

`render.respond` installs exactly one status, one `content-type`, and one body
under the host message limits provided by the request context. `render.respond_with_limits`
accepts an explicit `message.Limits` when narrower constraints are required.
It refuses a committed response, a response that already carries a body or a
content type, a body whose generation is not the response generation, and a
reader whose limits or length exceed the configured response body limits. Every
failure restores the original status, field count, and field byte total.

### Escaping

Escaping is a separate, explicit call. Nothing is escaped implicitly.

- `render.escape_html` rejects invalid UTF-8 and every control code point except
  tab, newline, and carriage return. It escapes `&`, `<`, `>`, `"`, and `'`.
- `render.escape_json` rejects invalid UTF-8 and emits the interior of a JSON
  string. It escapes the quote, the backslash, the five short control forms, and
  every remaining control code point, `<`, `>`, `&`, U+2028, and U+2029 as
  `\uXXXX`, so the result is safe inside an HTML script element.

Both measure before they write. A destination too small returns
`ESCAPE_CAPACITY` with a written count of zero, and never a partial escape.
`render.escaped_html_bytes` and `render.escaped_json_bytes` report the exact
requirement without writing.

## Realtime channels

Every realtime kind shares one bounded `realtime.Queue`. The queue is linear and
compacts toward its start rather than wrapping, so an encoded frame is always
written into one contiguous range. Its capacity is the entire pending budget for
that channel; nothing else buffers.

`realtime.send` and `realtime.close` route through `realtime.Channel`, a value
vtable over a caller-owned `Stream` or `Socket`.

### Backpressure

A send that cannot fit returns `SEND_BLOCKED` and accepts nothing.

- `KIND_STREAM` is a byte stream. It accepts a prefix and reports the accepted
  count, so a partially accepted write is itself the backpressure signal.
- `KIND_SSE` and `KIND_WEBSOCKET` are message oriented. An event or frame is
  accepted whole or not at all.

The consumer decides when the queue drains. For a stream or event source the
consumer is the response body reader; for a WebSocket it is
`realtime.socket_drain`. A consumer that stops reading fills the queue and every
further send is refused. Nothing grows and nothing is dropped.

When the reader finds the queue empty and the producer has not finished, it
suspends with a fresh token. `realtime.stream_readable` reports when the channel
has bytes or has finished, and `realtime.stream_pending` names the token the body
owner must complete. `realtime.stream_finish` publishes end of body once the
queued bytes have been read.

### Cancellation and disconnect

`stream_send` and `socket_send` classify the cancellation scope before they touch
the queue and return `SEND_CANCELLED` for a cancelled or timed-out request. A
disconnect reaches the stream as `body.cancel_reader` or `body.timeout_reader`,
which discards the queue, marks the channel closed, and makes every later send
return `SEND_CLOSED`. A channel never reopens.

### Server-sent events

Event data may contain line breaks and nothing else outside the printable set.
Event names, identifiers, and comments must be single-line. Every field is
validated as strict UTF-8 before any byte is queued.

Encoding follows the event stream format exactly: an `event:` line when a name is
present, an `id:` line when an identifier is present, a `retry:` line when a
retry is present, one `data:` line per line of data including a trailing empty
line when the data ends in a line break, and one blank line to dispatch. The
media type is `text/event-stream; charset=utf-8` from
`realtime.event_stream_media`.

Heartbeats are explicit and caller-clocked. `realtime.stream_heartbeat` takes the
current monotonic `time.Instant` and emits a comment only when the policy's
`heartbeat_interval` duration has elapsed since the last heartbeat; otherwise it
returns `SEND_NOT_DUE` without queuing anything. An interval of zero disables
heartbeats. `realtime.stream_observe` records an unrelated send so a busy stream
does not also emit heartbeats.

### WebSockets

Negotiation and framing come from `mach-http`. `realtime.negotiate` forwards to
`http.websocket.negotiation.server`, which validates the HTTP/1.1 upgrade or the
HTTP/2 and HTTP/3 extended CONNECT and commits the response. Laurel adds no
handshake logic of its own.

`realtime.Socket` owns one `http.websocket.Encoder` and one
`http.websocket.Decoder` and no transport. Outbound frames are encoded into the
queue; the integration that owns the socket drains them. Inbound bytes arrive
through `realtime.socket_feed`, whose event borrows the supplied input until
`realtime.socket_release`. A held event blocks the next feed, so a slow
application applies backpressure to whatever owns the socket.

Close policy is explicit. A close code must be one the peer may receive: not
below 1000, not 1004, 1005, 1006, or 1015, not in the reserved 1016 to 2999
range, and below 5000. A close reason is bounded by
`Policy.max_close_reason_bytes`, never exceeds 123 bytes, and must be valid
UTF-8. Sending a close marks the channel closing and refuses every later send;
receiving the peer's close completes the handshake and marks it closed.
