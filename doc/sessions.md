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
name, value, path, or domain view.

The default cookie limits are 64 cookies, 128-byte names, 4096-byte values, 16
attributes, 128-byte attribute names, 1024-byte attribute values, 4096 bytes per
cookie, and 16384 bytes total. Production applications should normally lower
these to the limits accepted by their ingress path.

## Protected codec

`session.ProtectedCodec` supports AES-256-GCM and ChaCha20-Poly1305 through the
exact `mach-crypto` v0.5.0 API. A token contains a version, algorithm, key
generation identifier, 96-bit nonce, ciphertext, and 128-bit tag. The header
and the caller's context value are authenticated as associated data. Use a
stable tenant, application, host, or cookie-purpose value as context. A token
encoded for one context cannot authenticate in another.

The entropy callback must fill the entire requested output with cryptographic
randomness or return nonzero. Each encode claims its nonce before encryption.
The supplied nonce guard must reject reuse for the full key generation. Claims
remain live through the generation's decode deadline plus accepted clock skew,
not merely through the encoded session's expiry. The bounded in-memory guard is
suitable for one process when its capacity covers every token encoded during a
generation. Exhaustion fails closed. A deployment with multiple writers must
inject a shared atomic claim implementation or allocate disjoint nonce domains
per writer.

Caller-owned key generation storage transfers exclusive mutation rights to the
active `KeyRing`. Do not modify an item until `release_key_ring` returns. A
generation has an activation time, an exclusive encode deadline, and an
exclusive decode deadline. `rotate_key_ring` changes only the current generation
and accepts a key that can encode at the supplied time. Codec operations copy
one immutable key snapshot under the ring mutex, so rotation may run alongside
active encode and decode calls. Retired generations may
decode inside their bounded window and produce `needs_rotation`. Unknown and
inactive generations fail before plaintext release. `release_key_ring` wipes
all 32-byte key slots and invalidates the ring.

The public application callback ABI contains no secret-qualified pointers.
Each operation copies the selected key and plaintext into fixed-size
secret-qualified local storage before calling `mach-crypto`, then explicitly
zeroizes every byte on all exits. The caller-owned key slots are sensitive
memory despite their public ABI type. They must not be logged, copied, or made
concurrently accessible.

Encode and decode take Unix seconds explicitly. The codec enforces nonnegative
times, issued-at, not-before, expiry, maximum lifetime, configured clock skew,
and key windows. Decode authenticates before it evaluates encrypted session
metadata. Outputs remain byte-for-byte unchanged on authentication, semantic,
capacity, replay, and clock failures. Encode output cannot overlap the input
session record, identifier, or data. Decode identifier and data outputs must be
disjoint and cannot overlap the output session record. Decode may reuse token
input storage because the complete envelope is staged before plaintext release.

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
Success resets the persistence version and generation to zero, so the new
identity must be inserted rather than updating the old record. Applications
must regenerate after authentication or privilege changes, save the new
session, and delete the old identity. The source record, source identifier and
data, identifier output, session output, and active codec storage must not
overlap any writable output range. Regeneration snapshots the source record and
identifier before entropy is requested, and every invalid ownership shape fails
before entropy or output mutation.

## Store boundary

`session.Store` is the complete durable provider interface. `start` and `stop`
own provider lifecycle. `load`, `save`, and `delete` receive an optional
cancellation scope and must return `STORE_CANCELLED` without publishing output
when it is no longer active.

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

`MemoryStore` implements this contract over caller-owned fixed storage and a
mutex. Capacity is explicit. Concurrent updates with the same expected version
produce exactly one success. Stop wipes identifiers and application data before
releasing the lifecycle. Durable providers retain ownership of their internal
connections, allocations, transactions, and cancellation machinery.

Store result records and load buffers must not overlap their input views or
session records. Unsafe aliasing fails before any caller output is written.

## Lifecycle order

Initialize key generations, the key ring, nonce and replay guards, protected
codec, store, and manager in that order. Start the manager before admission.
During shutdown, stop admission, settle requests, stop the manager, release the
codec, release both guards, then release the key ring. Caller storage must
outlive every object that borrows it.
