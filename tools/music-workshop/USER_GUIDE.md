# Music Workshop user guide

An offline guide for musicians, testers and developers. No agent or online
service is needed to use the workshop. Help > User guide or F1 opens this guide.
Choose a topic on the left. Ctrl+F finds text; Enter finds the next match.
Copy guide copies the whole guide for saving or printing. Esc closes help.
This same USER_GUIDE.md file can be read in any text editor.

## Game song dictionary: choose music by name

Game code calls a stable song, for example `music_play(NA_BGM_GAME_OVER)`.
The dictionary selects BANK or CD. A CD route points to a named disc song,
such as GAME_OVER, whose physical track number lives in a separate disc map.
Reordering tracks does not require editing gameplay code.

1. In Game song dictionary, select the game song (for example NA_BGM_GAME_OVER).
2. Choose CD and a named disc song, or BANK and an existing sound bank.
3. Click Save song mapping. This replaces that song's route immediately.
4. Close Kronos, rebuild Clean and open game/build/game-clean.cue.

To publish new audio and its mapping together, select a sequence and choose
the intended Game song in the dictionary, such as NA_BGM_GAME_OVER. Choose
Generate to > CD-DA track (Red Book), give it a stable Bank name such as
MY_GAME_OVER, then click Generate / Publish. This saves the audio, named CD
entry and selected song's CD route together. No separate Save song mapping
step is needed. A game BANK destination similarly publishes bank files and
sets the selected song's BANK route. Generate to determines the published
source; the dictionary's source/target controls are for mapping existing audio.
Other songs' routes stay unchanged, but songs sharing the overwritten audio
will hear its new version. Reusing a CD name replaces its audio in place.
Validation/render failures leave game files unchanged; ordinary publish write
failures roll back replaced files. Rebuild Clean after publishing.
Do not use a track number as the song's name.

The dictionary is game/assets/audio/songs.json. Each song has a permanent
song constant and numeric ID, an explicit src (BANK or CD), and either bank
or cd. The CD field is a name from game/assets/audio/cdda_tracks.json, never N.
Commit these source files, not generated headers. Do not renumber song IDs.
The three current fanfare/death callers can use BANK or CD. Title, area themes
and current timed cutscene-bank callers require BANK; their source picker
offers only BANK because those paths need data streaming or timed bank stops.
Adding a new game song requires a dictionary entry and a game call site.

For developers reordering a disc: change track fields in cdda_tracks.json,
keeping numbers consecutive from 2. Keep each name attached to its sequence
and soundfont. Rebuild Clean. Constants and song routes regenerate; the audio
cache checks track identity, sequence, soundfont, samples and renderer content,
so stale TRACKnn.BIN files cannot silently keep the old song. Cue generation
uses only declared tracks and fails if a declared audio file is missing.

## 1. First successful bake

1. Open tools/music-workshop/open-music-workshop.bat.
2. Type 75 in Filter and select sequence 75, NA_BGM_DEKU_TREE_CS. This is the
   Deku Tree cutscene cue, not the dungeon's area theme. It is a useful first
   example because the current baker supports it.
3. Set Bank name to DEKU_TEST. Clear Soundfont, Loop label, Sample budget and
   Voices for defaults. Leave Keep the intro/loop point off for this first test.
   Keep Generate to set to Workspace revision for this example.
4. Click Inspect. Wait until the status says Inspected. Read the result below
   the options: duration, memory use, voices and any omitted effects.
5. Click Preview WAV. Wait for your normal audio player to open. This action
   also saves a complete bank revision, not just a temporary WAV.
6. Listen for missing instruments, cut-off notes, wrong pitch and harsh peaks.
   The preview contains at most the first 80 seconds of one rendered pass.
7. Click Open workspace. Open DEKU_TEST and its newest timestamped folder.
   Your five output files are there. Preview WAV has already exported them;
   Generate / Publish makes another revision if you want one.

If the example fails, see Troubleshooting. Browsing and exporting do not require
compiling or running the Saturn game.

## 2. What the workshop can do

The workshop reads extracted OoT US NTSC 1.2 sequence commands and instrument
samples. It converts one sequence into samples and note/envelope data for the
existing Saturn SCSP music player, and renders a WAV for listening on the PC.

It is not a MIDI/WAV importer, a piano-roll editor or a recorder.
Generate to can replace an existing game music slot. You cannot compose notes
or arrange songs inside this GUI, or create a new runtime music slot.
Soundfont selection changes the source instruments; it does not edit notes.
Generated WAVs are previews, not CD-DA tracks automatically added to the game.

Some sequences use commands or instrument layouts the baker does not support.
A supported sequence may still omit effects listed in the inspection result.
Successful conversion means data was produced, not that it sounds identical
to the N64 original or has been verified on Saturn.

## 3. Setup on another developer's PC

Keep the whole repository checkout: the workshop imports the shared audio
builder and path configuration code. Copying only music_workshop.py will fail.

Install Windows Python with Tkinter. The BAT uses python and pythonw.exe from
PATH, so these must refer to that installation. The workshop itself does not
need Pillow. Other project tools may need additional dependencies.

From the repository root, these commands help diagnose a launch failure:

    python --version
    python -c "import tkinter"
    python tools/music-workshop/music_workshop.py

The last command keeps errors visible in a console. A configured Python path in
the game launcher does not change the workshop BAT's PATH-based Python choice.

Open launch-game.bat > Config > Paths, set the OoT decomp checkout, then save.
The workshop looks for an existing audio extraction in this order:

    <oot_decomp>/extracted/ntsc-1.2/assets/audio
    <repository>/shared/build/audio-source/extracted/assets/audio

The selected audio directory needs sequences, soundfonts and the samples those
soundfonts reference. A ROM alone is not an audio extraction. The workshop does
not extract it or download missing samples. After changing the configured source
path or creating an extraction, close and reopen the workshop.

For developers preparing extraction: shared/tools/extract_title_source.py has
--oot-root and --out arguments and unpacks the code/Audiobank/Audioseq/Audiotable
segments. The decomp's tools/extract_audio.py then converts those segments to
the sequence/XML/sample tree. Use its --help for that checkout's environment
and arguments. legacy/libyaul/docs/AUDIO.md describes the two-stage process,
but its old title-screen paths are historical; use the current shared paths
above. General workstation setup lives in tools/launcher/SETUP.md.

## 4. Catalog and buttons

Filter: matches decimal sequence number, sequence name or Already in game text.
It filters the visible list, not what Check all checks.

Seq: original sequence number. NA_BGM name: the symbolic name from the decomp.
If names are unavailable, a seq_N name can still identify the sequence.
Soundfont: the instrument bank declared in its source. Loop: detected sequence
jump label, or from the top when none was found. Bytes: source sequence file
size, not the generated PCM size or Saturn memory cost.

Already in game: a built-in reference list of existing uses. It is not a live
scan of your current ISO, and does not change after exporting a bank.
Bakes?: blank until Check all; yes means conversion succeeded with defaults.
It is not a listening verdict or a guarantee the bank fits game integration.

Inspect: interprets and bakes in PC memory and displays a report. Writes no bank
revision. It does not play audio.

Preview WAV: writes a complete revision and opens preview.wav in the default
Windows audio player. Stop playback in that player; the workshop has no Stop
button. It bakes the settings captured when you click it.

Generate to: choose Workspace revision or an existing game music target.
The target's source folder is shown below the selector. Title uses the shared
title asset folder; the other targets live under game/. Bank name applies only
to workspace exports; a game target fixes the required filenames/C prefix.

Generate / Publish: with Workspace revision, writes a revision including a
WAV. With a game target, replaces its PCM, levels, score header and manifest
directly, without an overwrite prompt. No WAV is written into the game folder.
Rebuild Clean to update the disc. Preview WAV always uses the workspace,
even when Generate to names a game target. No compile/play step is automatic.

Check all: tries the full catalog with default settings, regardless of Filter
or typed overrides. It asks before starting, may take minutes and writes no
bank revisions. For a no result, select the sequence and click Inspect to see
the precise reason. Results are held in memory for this workshop session.

Open workspace: opens the export root in Explorer, creating it if necessary.
Refresh: rebuilds the catalog list and resets the selection's inspection display.
It does not rediscover a changed configured source location.

During work, action buttons are disabled. There is no Cancel button. Let a bake
finish before closing; closing mid-export can leave an incomplete revision.
Help remains available while the main buttons are busy.

## 5. Options and reliable comparisons

Before switching songs, check EVERY field. Typed options carry over to the next
selection. Bank name is auto-filled only when it is empty; it may still name
the previous song. Clear fields deliberately when returning to defaults.

Preview WAV and Generate / Publish always bake the settings captured when
clicked. Inspect is useful to review limits first, but no stale inspected result
is reused. Edits made during an operation apply to the next operation only.

Bank name: output folder and C symbol prefix. Spaces/punctuation become
underscores and letters become uppercase. For game integration, begin with a
letter, use only letters/digits/underscores, and match the expected bank prefix.
Changing the name does not change the song. For game exports, Generate to picks
the assignment and canonical name; the typed Bank name is ignored.

Soundfont: decimal instrument-bank ID. Blank uses the source declaration.
Another bank may use different instrument numbers or lack a required sample.
An override that converts successfully can still sound completely different.

Loop label: exact source label, for example SEQ_0082. This is not a time in
seconds or a frame number. Blank uses automatic detection; blank does not mean
disable looping. Look at sequences/seq_N.seq to confirm a custom label exists.

Keep the intro/loop point: writes the detected intro boundary as LOOP_FRAME in
the score header. On repeat, the game resumes there. Off writes LOOP_FRAME=0,
so the entire score repeats from its beginning. It does not remove the intro
from the first pass. If no intro boundary is detected, it may still be zero.
The WAV is a single-pass host render; toggling this box does not audition the
game's repeat transition. Check that transition in Kronos or on Saturn.

Sample budget: a count of 16-bit samples, not bytes or sample rate. Blank uses
the shared builder default, currently 159600 samples (319200 bytes before small
per-sample guards/rounding). Reducing it resamples instruments more heavily,
saving PCM memory at the cost of detail. Try 120000 for a smaller comparison.
This is not a volume or playback-speed control. Use positive decimal integers;
zero currently falls back to the default.

Voices: simultaneous note slots, currently 24 by default. Fewer voices can cut
off overlapping notes or release tails. Keep at most 24 for this game: slots
24 through 31 belong to action/Navi sounds. A larger number in this field does
not reserve more hardware voices or update the runtime safely. Use blank for
the normal configuration.

Comparison recipe: export with defaults as MYSONG_DEFAULT, change only Sample
budget to 120000, click Inspect, export as MYSONG_SMALL, then compare both WAVs
and manifests. Keep the revision folders until you have chosen the result.

## 6. Reading results and limits

Seconds/frames: length of the rendered score at a 60 Hz timeline. The runtime
frame count must be 1..65535. A score longer than that needs deliberate changes
to the source/loop or player; renaming it or shrinking PCM does not fix length.

Notes: interpreted musical events. Triggers: scheduled voice/sample starts.
PCM: instrument sample-bank bytes. Levels: one envelope byte per voice per
frame; this data has its own RAM cost separate from the PCM sample budget.
Peak voices: maximum simultaneously audible slots used in the bake.

OVER BUDGET and does not fit are reports. Workspace exports may contain those
warnings. Direct game export rejects an invalid voice/frame count, sample-budget
overrun, bad envelope length or PCM crossing the game's sound-RAM boundary.
Lower the relevant setting and re-inspect, or fix the unsupported source case.

The game reserves sound RAM below 0x50000 for music; samples start at 0x1000.
Thus sample_base + pcm_bytes must fit the game's MUSIC_SAMPLE_LIMIT, currently
0x50000. The workshop's sample-budget report does not check the
shared trigger carve or total game Work RAM. Direct game export checks the
sound-RAM boundary too; the final build still checks trigger/Work RAM limits.

No SCSP counterpart, dropped: source effects omitted by the current converter.
Other unsupported commands stop conversion instead. Listen to the preview and
read the manifest; do not treat either kind of result as exact N64 playback.

## 7. Saved files and backup

Workspace exports and Preview WAV go NEXT TO the repository, not inside it:

    <repository parent>/workspace/music/<NAME>/<timestamp>-<unique ID>/

Open workspace resolves the actual location on your PC. Every Preview WAV or
Generate / Publish with Workspace revision creates a new revision. Existing revisions are retained.
These exports are outside the repository and are not backed up by committing
the game's Git checkout. Copy chosen revision folders to your normal backup.

Each complete revision contains:

- NAME_PCM.RAW: big-endian signed 16-bit mono instrument samples.
- NAME_LEVELS.RAW: frame-by-frame volume envelopes for all configured voices.
- name_score.h: generated sample descriptions, triggers, counts and loop frame.
- name_manifest.json: sequence ID/hash, source path, budgets and limitations.
- preview.wav: stereo PC listening preview, up to 80 seconds of the first pass.

Keep PCM, levels and the header from the SAME revision. Mixing them can give
wrong notes, lengths, sample addresses or silence. Keep the manifest beside
your chosen files so another developer can identify the source and settings.
If export was interrupted or an error appeared, make a fresh complete revision.

Direct game exports overwrite the selected bank's four source files inside the
checkout. Generation completes before replacements begin; ordinary write errors
roll back completed replacements. Review/save these changes with Git. No commit
or automatic backup revision is created. A Clean build is still required.

House/shop exports persist in game/assets/audio/interiors. The normal build
copies them to generated assets instead of rebaking the originals. To return
to stock after first installing an override, remove that bank's four override
files and rebuild; do not leave a partial override set. To undo a later edit,
restore the four files from the desired Git revision and rebuild.

## 8. Replace forest music in the game

This is a concrete workflow for an existing bank. Start from a working game checkout.
Paths below are relative to the repository root.

1. Pick a supported song, choose Generate to > Kokiri Forest, and leave Voices at the
   default 24. Set the intro option for your intended repeat behavior.
2. Inspect, preview, and choose one complete revision with acceptable limits.
3. Click Generate / Publish. It replaces KOKIRI_PCM.RAW, KOKIRI_LEVELS.RAW,
   kokiri_score.h and kokiri_manifest.json in game/levels/kokiri/assets/audio.
   Bank name is fixed by the target, so no renaming or manual copying is needed.
4. Review the changed bank files in Git and retain the version you want.
5. Close Kronos before rebuilding its mounted image. From the repository root:

       .\game\build.bat -Variant clean

6. Check the build finishes successfully and all memory/asset guards pass.
   game/build.sh stages KOKIRI_PCM.RAW as FOREST.PCM and KOKIRI_LEVELS.RAW as
   FOREST.LVL. It also regenerates MUSICTRG.BIN from the chosen score header.
7. Launch game/run-kronos-clean.bat. Enter the forest, listen beyond the first
   loop, enter/leave a house, and check music changes plus action sounds.
8. To undo, restore the bank's files from your chosen Git revision and rebuild Clean again.

This recipe preserves the existing KOKIRI C symbols and forest assignment.
For house/shop, select their game target: the workshop stores a persistent source
override instead of editing game/build/generated. Editing game/build/cd alone is temporary;
the next build stages source assets over it. Keep the accepted source bank
and the build recipe together.

## 9. Add a new game bank

This is a code/build task, not a workshop button. Use the existing forest bank
as a template and keep the following changes together:

1. Choose a stable bank name and source asset folder. Add the generated header
   to compiler include paths in game/makefile if the folder is new.
2. In game/src/music_banks.h, declare the bank. In music_banks.c, include its
   score header and define music_bank_t with matching PCM/LVL disc names,
   sample table, trigger count, frames, loop frame, voices, base and byte sizes.
3. Add it to music_banks.c's banks and counts arrays. Add the matching trigger
   header/prefix to BANKS in game/tools/build_cart_tables.py in the SAME order.
   The runtime binds trigger pointers from MUSICTRG.BIN; a score header alone
   is not sufficient. Keep the cart-table capacity check enabled.
4. In game/build.sh, stage its PCM and levels under the exact disc filenames
   used by the bank definition. Use short ISO-compatible names like NEW.PCM
   and NEW.LVL. Arrange generation/copying BEFORE build_cart_tables.py runs.
5. Wire the intended scene/cutscene to that bank. Area selection currently
   lives in scene_music() in game/src/recomp.c; cutscene bank selection is in
   game/src/cutscene.c. Creating a bank does not select it automatically.
6. Rebuild Clean and check the target map, file capacity, trigger carve and
   sound-RAM limits. Listen in the actual scene and across music transitions.

Only one music sample bank is resident at a time. Music streaming can keep one
CD handle across frames; the project requires at least two filesystem handles
so scene/cutscene reads can coexist. Do not remove that setting to save RAM.
Use CD-DA only during the project's approved frozen-world sequences, not as a
shortcut for live exploration music. Read DOSEI-LEGEND-BIBLE.md before changing
the audio architecture. None of these integrations are performed by this GUI.

The game mutes normal background music while a CD track plays, then fades it
back over 0.5 seconds after the track ends. This affects music only; SFX and the
CD track remain audible. Test this handoff when changing audio playback code.

## 10. Troubleshooting

Window does not open: run the console launch command in Setup. Check both
python and pythonw.exe are on PATH and Tkinter imports successfully.

No US 1.2 audio extraction found: check the two source paths in Setup, including
the extracted sequences/soundfonts/samples directories. Configure the decomp
path and restart the workshop. Refresh alone will not select a new source.

Empty list after filtering: clear Filter. A filtered-out selection cannot bake.

Not supported yet / unsupported opcode: Inspect names the command the current
interpreter lacks, such as rldchan or bend. Check all helps find another usable
sequence. A larger memory budget cannot implement an unsupported command.
Developer entry point: shared/tools/build_title_audio.py. Preserve an example
sequence and add a focused regression when implementing command semantics.

Soundfont mismatch / split-range instruments / missing sample: return Soundfont
to blank and inspect again. Confirm the extraction is complete. Another font
may bake, but different instruments are an audible change, not a parity fix.

Infinite release unsupported: the envelope format is not handled by the baker.
Choose another supported source or implement the required envelope behavior.

Changed options but WAV sounds unchanged: click Preview WAV again. Settings are
captured at click time. Check the latest revision's manifest and that your audio player opened
the new path, not an older file with the same preview.wav filename.

Preview stops at 80 seconds: this is the current preview limit, not necessarily
the score length. Inspect shows the complete rendered duration. Repeat-loop
behavior must be checked in the game.

Preview file saved but player does not open: Open workspace, find the latest
revision and open preview.wav with an installed WAV player. Set a default WAV
application in Windows if desired. Check files before generating duplicates.

Missing notes or instrument tails: compare defaults; check peak voices, omitted
commands and any soundfont override. A successful bake can reclaim quiet release
tails when voices are full. Host rendering also differs from real SCSP mixing.

New game bank is silent or old music remains: check the selected bank, matching
header/PCM/levels revision, staged filenames and regenerated MUSICTRG.BIN.
Reopen the rebuilt image. Check whether a normal asset builder overwrote your
manual files. Never bypass a failed file-size or sound-memory check.

Blue screen on a scene change: record the exact error/function and timing.
GFS_Open failed is different from file not found or out of memory. Check the
two-handle CD rule, matching disc assets and memory guards in the Bible.

## 11. Command line and sharing a result

From the repository root:

    python tools/music-workshop/music_workshop.py --bake DEKU_TEST 75
    python tools/music-workshop/music_workshop.py --survey
    python tools/music-workshop/music_workshop.py --smoke-test

--bake uses defaults and exports a revision without opening the main window.
--survey prints supported/unsupported results for the entire catalog.
--smoke-test opens a hidden GUI, checks that sequences are listed, then exits;
it needs the extraction but writes no audio assets. CLI overrides for budgets,
voices and loop preservation are not exposed; use the GUI for those settings.

When handing a result to another developer, include the complete chosen
revision, sequence ID, intended scene, the settings you changed, what you heard,
and whether you tested only the PC preview or also Kronos/Saturn. For a failure,
include the exact error and relevant source filename. That gives a human enough
information to reproduce it without an agent conversation.
