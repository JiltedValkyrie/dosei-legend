# Shared game resources

`lib/` contains reusable camera, collision and bank-agnostic SCSP music code.
Camera/collision use main's logic, not performance ablations. The music player
depends on Jo/SGL; game-specific bank definitions remain in `game/src/`.

`assets/static/ui/` holds UI artwork; `assets/audio/title/` holds title audio,
score and provenance. The forest-specific bank lives with the Kokiri level.
`tools/` holds reused extraction/export helpers. `build/` is ignored extraction
and cache output, not hand-edited asset source.
