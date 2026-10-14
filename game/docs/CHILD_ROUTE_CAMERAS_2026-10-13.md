# Child route camera, courtyard and ocarina evidence

Implementation and isolated validation, 2026-10-13. Full image and human
runtime acceptance remain open. Shared current scope and integration gates:
[child route plan](CHILD_ROUTE_DODONGO_PLAN.md).

## Camera and scene ownership

`bridge_cutscene_camera.cpp` retains source camera storage, queue/status/copy/
finish, source Player camera seeding and joined eye/at/FOV/roll/letterbox views.
`onepoint_sources.py` emits exact source setup cases and only the needed
Unique9/Demo5/Demo9/Unique6 engines into each OAP. No action-case caps are cut.
Attention retains source category order, deduplication, chime and release.
Screen projection uses the live Saturn view rather than an uninitialized N64
matrix. Required DC stair spline, chest fixed shot, Darunia, child warp, owl,
Goron props and shooting/bowling cameras have admitted setup cases.

Pack services are versioned, pointer-checked against their own text extent,
published only after successful pack initialization and cleared before unload.
The subsequent NPC view service uses the same ownership contract; consult the
current header rather than reusing an earlier serialized header size.
Host camera data is cached after join and cannot read live slave state.
The source destination's next cutscene index travels through scene transition
and reloads the correct source layer. Scene script command ABI is asserted;
IEEE camera words are converted offline to Q16. No empty-script success path.

`run_cutscene_camera_probe.sh`: 12 executing groups pass, including owl
enter/hold/leave; DC platform no-copy release; stair Demo9 plus queued1020;
Darunia spherical/reward hold; warp9703 tracking rising Player; real source
attention ordering/chime/Player release; courtyard main camera; shop camera;
letterbox and source spline STOP/Player-relative points. Latest isolated audit:
44 resident and40 packed native hardware products, zero forbidden helpers.
Collision fixture uses no-hit scenery; it does not establish scene collision
or runtime framing acceptance.

`run_cutscene_script_probe.sh`: six complete source scripts pass, executing
source z_demo handlers and real source spline. Darunia runs through frame710;
Epona transfers its destination; courtyard Ganondorf reaches walk/kneel/look
cues; Impa emits Lullaby teach/playback and Field destination875; the Three
Goddesses deliver all three cues/Triforce and courtyard-letter destination740.
DC opening reports its source title command. Textbox waits are fixture-driven;
title pixels and live lesson interaction are separate gates.

`test_onepoint_sources.py`: three tests validate admitted actor camera IDs,
attention5010 and extraction of both braced and unbraced source cases.
Adult Ruto warp9704/9705 remains outside the admitted child path.

## Owl and courtyard sprites

`owl_sources.py` keeps real EnOwl Field talk/repeat/accept/switch/departure and
DMT magic/transport predicates. Five clips with perch/flight/head-flip variants
produce ten sheets,12 keys,124096 bytes in the isolated bake. Source pose arrays
and limb/head tracking are absent. Host owl retirement is conditional on actual
source admission; scene-load ordering preserves that condition. Two executing
source owl checks pass. Existing fallback timing/facing checks remain useful
only for scenes where fallback ownership is still selected.

`courtyard_sources.py` keeps EnZl4, DemoIm and window EnViewer type8 actions.
Zelda's15 required root-motion clips use1002 bytes of offline XZ anchors;
no runtime joint/morph evaluation or root motion double-application. Every
clip is baked:33 Zelda,10 Impa,4 Ganon. Initial isolated47-sheet bake517084
bytes is evidence of coverage, not an approved scene memory footprint.
Budgeted final archive density may differ. Four source/handshake/root-motion
tests pass. Four owl/courtyard TUs compile for host/SH-2, with no forbidden
helpers. Original item parent handshakes and Lullaby source flags remain.

## Ocarina and audio

`ocarina_memory_source.py` extracts the actual source generator and round
lengths5/6/8; bounded storage replaces the unrelated full audio song array.
Gameplay RNG replaces the N64 audio-thread RNG. The source first-note
negative-index read is guarded. Generated notes populate the compact bridge
recognizer without changing source message/NPC rewards.

`bridge_message.cpp` admits memory-song playback and flag0xA000, supports
source playback repetitions and strict lesson/memory-note failure. Explicit
reset clears stale source Player ocarina ownership. Existing Saturn input,
freeplay trailing-note recognition, known-song restrictions and repeated
Time/Sun/Saria behavior remain covered.

`test_ocarina.py`: six tests pass. The actual z_message memory cases,
Message_UpdateOcarinaMemoryGame and EnSkj_WaitForPlayback execute through all
three rounds, source win dialogue0x10BF, wrong-note failure0x102D and completion
waits. Saria/Epona/Lullaby lesson retry and twice-repeated demonstrations pass.
This is source choreography execution, not a rendered minigame playtest.

`build_action_audio.py` bakes source drum-routed METRONOME, METRONOME_2 and
the held METRONOME_LV. Authored silence preserves72/36 source-sequence ticks
and the held rhythm period. Generated PCM duration header supplies15/8 game
ticks to Audio_IsSfxPlaying; timer starts only when a host SFX is queued and
resets at scene/ocarina reset. Both Audio_PlaySfxGeneral and the conditional
audio path notify it. Ocarina notes retain slot29, beats28/26.
`test_action_audio.py`:26 tests pass, including original bank/register routing,
exact generated beat PCM, duration header and held-loop period. Latest bank
158804 bytes leaves37804 bytes for the selected area bank. Existing area-tail
trimming is reported by the generated manifest; final field/boss banks and
the separately streamed full chest jingle require combined validation.

## Explicit remaining limits

Source quake requests and some cutscene environment presentation still lack
their final backend; title command execution is not title drawing. Source
story state is preserved and unsupported effects are reported. Custom long
scarecrow recording/playback is outside the admitted child route. Final
pack exports/link, scene+actor+effects heap/VRAM budgets, full target image,
human camera framing and complete fresh-file story acceptance remain open.
