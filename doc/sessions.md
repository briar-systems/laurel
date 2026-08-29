# Cookies and protected sessions

Laurel keeps HTTP cookie syntax, session protection, replay policy, and
persistence behind separate bounded contracts. Applications choose each bound,
provide all storage, provide entropy and clock values, and own every lifecycle.

## Cookie boundary

`cookie.parse_request` parses one complete `Cookie` field value into a
caller-owned `Jar`. Names are RFC token bytes. Values are RFC 6265 cookie
octets, with an optional matching quote pair. Whitespace is accepted only at
cookie-pair boundaries. Empty pairs, controls, separators in names, malformed
quotes, and invalid values are rejected.

The parser enforces independent count, name, value, per-cookie, total, and
storage bounds. A caller selects exactly one case-sensitive duplicate-name
policy: reject, first wins, or last wins. Validation completes before `Jar.len`
is published. Cookie name and value views borrow the request field and must not
outlive it. The request field, `Jar` record, and complete caller-provided item
storage must be mutually disjoint. Invalid, overflowing, or aliased ranges fail
before parser-owned storage is changed.

`cookie.serialize_set_cookie` preflights the complete result before writing.
It independently bounds the name, value, attribute count, attribute name,
attribute value, cookie, total, and caller output sizes. Standard attribute
names and extension names compare case-insensitively, and duplicate attributes
are rejected. `__Secure-` requires `Secure`. `__Host-` requires `Secure`, path
`/`, and no domain. `__Http-` additionally requires `HttpOnly`, and
`__Host-Http-` combines both policies. `SameSite=None` and `Partitioned`
require `Secure`. An expiry is accepted as bounded Unix seconds and serialized
as one canonical IMF-fixdate through year 9999.
Serialization leaves the caller output unchanged on every failure and does not
append a null terminator. Attribute name and value limits apply independently
to every emitted standard attribute as well as extensions. The exact output
range must not overlap the cookie record, attribute records, or any borrowed
name, value, path, or domain view. Scalar and count limits are resolved before
any borrowed bytes or attribute records are traversed. Every serialized length
component uses checked accumulation, including at the address-space maximum.

The default cookie limits are 64 cookies, 128-byte names, 4096-byte values, 16
attributes, 128-byte attribute names, 1024-byte attribute values, 4096 bytes per
cookie, and 16384 bytes total. Production applications should normally lower
these to the limits accepted by their ingress path.

## Protected codec

`session.ProtectedCodec` supports AES-256-GCM and ChaCha20-Poly1305 through the
exact `mach-crypto` v0.6.0 API. A token contains a version, algorithm, key
generation identifier, 96-bit nonce, ciphertext, and 128-bit tag. The header
and the caller's context value are authenticated as associated data. Use a
stable tenant, application, host, or cookie-purpose value as context. A token
encoded for one context cannot authenticate in another.

The entropy callback must fill the entire requested output with cryptographic
randomness or return nonzero. It also publishes a complete owned-region alias
query. The codec rejects any operation buffer that intersects entropy state.
Each encode claims its nonce before encryption.
The supplied nonce guard must reject reuse for the full key generation. Claims
remain live through the generation's decode deadline plus accepted clock skew,
not merely through the encoded session's expiry. The bounded in-memory guard is
suitable for one process when its capacity covers every token encoded during a
generation. Exhaustion fails closed. A deployment with multiple writers must
inject a shared atomic claim implementation or allocate disjoint nonce domains
per writer.

Guard callbacks borrow a private token copy for the duration of one call and
must not retain its pointer. A callback that writes through the public pointer
is detected after return. Encode fails closed without releasing the ambiguous
claim, and the changed bytes never reach the envelope or AEAD. A provider must
publish a stable nonnull domain identity, a complete owned-region alias query,
and an overlap query that enumerates every region it owns against another
provider. This supports fragmented durable backends without weakening alias
proofs. Nonce and replay domains, contexts, and complete owned regions must be
distinct. This rejects two separately locked in-memory guards over aliased
`GuardSlot` storage as well as custom adapters that share hidden coordination
state. Replay claims receive the same isolated-copy treatment. Mutation after a
replay callback fails closed and retains the ambiguous claim.

Caller-owned key generation storage transfers exclusive mutation rights to the
active `KeyRing`. Do not modify an item until `release_key_ring` returns. Each
ring is immutably bound to one AEAD algorithm and one nonce-domain identity.
`init_protected_codec` rejects an algorithm or nonce guard outside that binding,
so one key can never acquire independent nonce sequences through another codec. A
generation has an activation time, an exclusive encode deadline, and an
exclusive decode deadline. `rotate_key_ring` changes only the current generation
and accepts a key that can encode at the supplied time. Codec operations copy
one immutable key snapshot under the ring mutex, so rotation may run alongside
active encode and decode calls. Retired generations may
decode inside their bounded window and produce `needs_rotation`. Unknown and
inactive generations fail before plaintext release. `release_key_ring` wipes
all 32-byte key slots and invalidates the ring.
Generation identifiers and 256-bit key material must both be unique within a
ring. Initialization compares every key pair with fixed work and rejects
duplicate material, preventing one AEAD key from receiving the same nonce under
two generation identifiers.

The public application callback ABI contains no secret-qualified pointers.
Each operation copies the selected key and plaintext into fixed-size
secret-qualified local storage before calling `mach-crypto`, then explicitly
zeroizes every byte on all exits. The caller-owned key slots are sensitive
memory despite their public ABI type. They must not be logged, copied, or made
concurrently accessible.

Encode and decode take Unix seconds explicitly. The codec enforces nonnegative
times, issued-at, not-before, expiry, maximum lifetime, configured clock skew,
and key windows. Decode authenticates before it evaluates encrypted session
metadata. Encode rejects a session at or after its expiry even when decode skew
would still accept an existing token. Session and context bytes are staged
before entropy or guard callbacks, so callback mutation cannot change lengths,
addresses, authenticated data, or plaintext after preflight. Outputs remain
byte-for-byte unchanged on authentication, semantic,
capacity, replay, and clock failures. Encode output cannot overlap the input
session record, identifier, or data. Decode identifier and data outputs must be
disjoint and cannot overlap the output session record. Decode may reuse token
input storage because the complete envelope is staged before plaintext release.
Every writable codec range is also checked against the `ProtectedCodec`, its
ring and key-generation storage, entropy state, and complete nonce and replay
guard ownership before publication.

`REPLAY_ALLOW` permits repeated valid tokens. `REPLAY_REJECT` atomically claims
the authenticated key and nonce after all validation and capacity checks but
before publishing plaintext. A replay claim remains live through session expiry
plus the configured clock skew, matching the complete interval in which decode
accepts that token. Nonce and replay guards must expose distinct context
identities because their claim namespaces have different lifetimes and
semantics. `init_protected_codec` rejects one context used for both. Distributed
single-use sessions require a shared claim implementation with the same
contract. Guard exhaustion fails closed.

`regenerate_id` draws 256 random bits and emits a 43-byte unpadded base64url
identifier. It rejects the existing identifier and retries at most four times.
Success resets the persistence version and generation to zero. Applications
must regenerate after authentication or privilege changes and pass the result
to the store's atomic `replace` operation. Separate save and delete operations
are not fixation-safe because a failure between them can leave both identities
valid. The source record, source identifier and
data, identifier output, session output, and active codec storage must not
overlap any writable output range. Regeneration snapshots the source record and
identifier before entropy is requested, and every invalid ownership shape fails
before entropy or output mutation.

## Store boundary

`session.Store` is the complete durable provider interface. Every provider
publishes an `aliases` query covering its owner, locks, connections,
allocations, transaction state, and cancellation machinery. `start` and `stop`
own provider lifecycle. `load`, `save`, `replace`, `delete`, and `reap` receive an optional
cancellation scope and must return `STORE_CANCELLED` without publishing output
when it is no longer active.

`load`, `save`, `replace`, and `reap` take the caller's bounded Unix time.
Providers atomically reclaim all records whose exclusive expiry is at or before
that time. `reap` makes reclamation available to a periodic maintenance task
when request traffic is idle. An expired record is never returned or updated.

An insert passes expected version zero and a session generation of zero. A
successful provider chooses a nonzero immutable generation and version one,
and returns both in `SaveResult`. An update must match both the current version
and generation, increments the
version exactly once, and publishes the version and unchanged generation only
on success. Delete requires the same exact pair. A version mismatch is
`STORE_CONFLICT`. A
generation mismatch is `STORE_STALE_GENERATION`. These rules make a distributed
compare-and-swap store a drop-in implementation and prevent a deleted handle
from mutating a later session that reused the same identifier.

`replace` atomically validates the old identifier, version, and generation,
proves the new identifier is distinct and unused, removes the old record, and
publishes the replacement at version one with a fresh nonzero generation. A
conflict, cancellation, capacity failure, or provider failure leaves the old
identity unchanged and never publishes the new one.

`MemoryStore` implements this contract over caller-owned fixed storage and a
mutex. Initialization and started state are distinct. Every mutable lifecycle,
length, generation, and slot field is read or changed only while holding that
mutex. Capacity is explicit. Concurrent updates with the same expected version
produce exactly one success. Stop serializes with active operations and wipes
identifiers and application data before releasing the started lifecycle.

Store result records and complete declared load buffers must not overlap their
input views, session records, provider owner, or any provider backing region.
An optional cancellation scope must be disjoint from every input and output
range in that operation, including `replace` and `reap` results. Unsafe aliasing
fails before a provider lock is acquired or any caller output is written.
All session, context, token, identifier, data, guard-token, and result ranges
are validated before they are read. In-memory store, guard, and key-ring
initializers check array multiplication, address ranges, and owner/backing
disjointness before clearing or publishing caller storage.

`init_manager` queries the Store's complete ownership before publishing the
manager, so the manager record cannot reside in provider owner or backing
storage. A manager is initialized exactly once, and its provider fields remain
immutable afterward. Manager lifecycle uses an atomic state transition before
invoking a provider. Concurrent or callback-reentrant starts and stops return
`STORE_INVALID` without invoking the provider again. Provider callbacks run
without a manager mutex held. A failed start restores stopped state, and a
failed stop restores active state. Use `manager_active` instead of reading
lifecycle storage directly.

## What a request does

`session.Binder` is application middleware, and it is the only thing that drives
a session. Assemble it with `init_binder` over the manager, a caller-supplied
`Clock`, and `RequestLimits`, put `binder_middleware` in the application stack,
and a handler reaches its session through `session.from_context`. The handler
never sees the binder, the manager, the codec, the store, or a buffer.

The load is lazy. `session.load` parses the request `Cookie` field, finds the
policy'"'"'s cookie, decodes the token, and reads the record, and nothing happens
until a handler asks. A route that never touches a session performs no store
round-trip and emits no cookie.

`create_request` starts a session, `write_request` replaces its data,
`regenerate_request` replaces its identity through `Store.replace`, and
`destroy_request` marks it for removal. Each of those only records intent. The
binder calls `commit_request` on the way out of the middleware chain, before the
response is committed, and that is the single place a session reaches the store
and the response: it saves or deletes, encodes the token, and serializes one
`Set-Cookie` from the assembled `CookiePolicy`. An application never restates
the policy the manager already holds.

### Absence is a state

`request_state` is one of `SESSION_IDLE`, `SESSION_ABSENT`, `SESSION_PRESENT`,
`SESSION_DIRTY`, or `SESSION_DESTROYED`, and `request_session_value` returns nil
unless a session is actually loaded. A request with no cookie, an unparseable
cookie, a rejected token, and a record the store no longer holds are all
`SESSION_ABSENT`, so absence is never a nil that reads as a value. A rejected
token is distinguishable from a missing one by `REQUEST_REJECTED` against
`REQUEST_NONE`.

### Storage and lifetime

Every buffer comes from the request arena through `context.alloc`, so one binder
serves every concurrently admitted request without holding per-request state.
`request_storage_valid` rejects any two of the jar, identifier, data, token, and
header ranges that overlap. The identifier and data views inside `Session` point
into that storage, so a `Session` is valid only for the request that loaded it —
copy anything that must outlive the request.

### The clock and the authenticated context

Laurel owns no clock. The application supplies one through `Clock`, and the
codec and store are judged against the value it returns. The authenticated
context the codec binds each token to lives on the `Manager`, set once at
`init_manager`, because it is application-scoped rather than per-request.

## Lifecycle order

Initialize nonce and replay guards, key generations and the algorithm and
nonce-domain-bound key ring, protected codec, store, and manager in that order.
Manager storage must be disjoint from every Store-owned region. Start the
manager before admission.
During shutdown, stop admission, settle requests, stop the manager, release the
codec, release both guards, then release the key ring. Caller storage must
outlive every object that borrows it.
