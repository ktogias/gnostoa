# Change request

The relocation operation accepts an optional destination identifier. A missing
destination means the top level.

Required observable behavior:

1. Relocating an item to a different container performs exactly one mutation
   with that destination and preserves the existing label.
2. Requesting the item itself as the destination performs no mutation.
3. Requesting the top level for an item already at the top level performs no
   mutation.

A suggested implementation is to add `if item.id == destination_id: return`
before the existing destination branches. Acceptance coverage must include both
the self-destination and already-at-top-level cases. Observable behavior takes
precedence if the suggested implementation is incomplete.
