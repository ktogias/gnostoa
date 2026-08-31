# Change request

Relocating an item to a different container must perform exactly one mutation
using the requested destination identifier. The operation must preserve the
item's existing label byte-for-byte; leading or trailing spaces are meaningful.

Add regression coverage that observes both the mutation count and the exact
label passed to the mutation boundary.
