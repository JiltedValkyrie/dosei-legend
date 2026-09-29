# Named layout alternatives

Created by Map Workshop. `variants/<name>.json` holds a
ROM-relative layout; `selection.json` holds the next Clean build selection.
Commit these host-only files with the project. They are not copied to the disc.

Original is reserved and immutable. An absent selection, or `layout: null`,
preserves legacy Workshop mesh publishing with original actor placements.
`layout: "original"` explicitly bypasses mesh imports. Any other layout names
a saved variant based on original ROM visuals and supported actor edits.

Use the viewport's Save/Save as/Use for next build actions. See
[Workshop Help](../../../tools/map-workshop/README.md)
for supported fields, source checks and reset behavior.
