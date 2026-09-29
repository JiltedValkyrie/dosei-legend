"""Browse the US 1.2 sequences and bake any one of them into a Saturn music bank.

All interpreting, soundfont loading, baking and WAV previewing is done by the
existing shared/tools/build_title_audio.py -- this module only finds the source
material, describes it, and writes workspace revisions or selected game banks.

Workspace exports make revisions. Explicit game targets replace the complete
source bank under its existing runtime names, ready for the next Clean build.

Offline tool. Floating point is fine here; none of this runs on the SH-2.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent / 'workspace/music'

# label, source directory, C prefix, PCM/levels filename prefix.
GAME_TARGETS = {
    'Title': ('shared/assets/audio/title', 'TITLE', 'TITLE'),
    'Kokiri Forest': ('game/levels/kokiri/assets/audio', 'KOKIRI', 'KOKIRI'),
    'Navi cutscene': ('game/assets/audio/cutscenes', 'NAVI', 'CSNAVI'),
    'Deku Tree cutscene': ('game/assets/audio/cutscenes', 'DEKU_TREE', 'CSDEKU'),
    'Nightmare cutscene': ('game/assets/audio/cutscenes', 'NIGHTMARE', 'CSGANON'),
    "Link's house": ('game/assets/audio/interiors', 'HOUSE', 'HOUSE'),
    'Kokiri Shop': ('game/assets/audio/interiors', 'SHOP', 'SHOP'),
}

sys.path.insert(0, str(ROOT / 'shared/tools'))
sys.path.insert(0, str(ROOT / 'tools/launcher'))
import build_title_audio as audio                                  # noqa: E402
import project_config                                              # noqa: E402

# Sequences the shipping builders already bake, so the catalog can say which
# music is spoken for. Kept beside the builders it mirrors; see the READMEs.
IN_GAME = {30: 'title', 60: 'kokiri forest', 31: "link's house", 85: 'shop',
           35: 'cutscene: nightmare', 74: 'cutscene: navi',
           75: 'cutscene: deku tree',
           0: 'sound effects', 109: 'fairy'}


def find_source(root=ROOT):
    """The audio extraction to browse, or None with a reason.

    Prefers the decomp's own extraction because it is the one the shipping
    builders default to; falls back to the project's local copy.
    """
    candidates = []
    try:
        decomp = project_config.read_paths(root).get('oot_decomp')
        if decomp:
            candidates.append(Path(decomp) / 'extracted/ntsc-1.2/assets/audio')
    except Exception:
        pass                       # A missing/!broken INI must not kill the GUI.
    candidates.append(root / 'shared/build/audio-source/extracted/assets/audio')
    for path in candidates:
        if (path / 'sequences').is_dir() and (path / 'soundfonts').is_dir():
            return path, None
    return None, ('No US 1.2 audio extraction found. Looked in:\n  '
                  + '\n  '.join(str(p) for p in candidates)
                  + '\nRun the extraction steps in legacy/libyaul/docs/AUDIO.md.')


def sequence_names(root=ROOT):
    """Sequence number -> NA_BGM_* name, read from the decomp's own table."""
    try:
        decomp = project_config.read_paths(root).get('oot_decomp')
        table = Path(decomp) / 'include/tables/sequence_table.h'
        text = table.read_text(errors='replace')
    except Exception:
        return {}
    names = {}
    for number, name in re.findall(
            r'DEFINE_SEQUENCE\s*\(\s*Sequence_(\d+)\s*,\s*(NA_BGM_\w+)', text):
        names[int(number)] = name
    return names


def soundfont_of(seq_path):
    """The soundfont a sequence includes, e.g. Soundfont_3.h -> 3, or None."""
    found = re.search(r'Soundfont_(\d+)\.h',
                      seq_path.read_text(errors='replace')[:400])
    return int(found.group(1)) if found else None


def loop_label_of(seq_path):
    """The label the sequence's own `jump` goes back to, or None.

    Read from the sequence rather than assumed: some cues reach `end` by
    themselves while others sit in a jump and play until the game stops them.
    """
    found = re.search(r'jump\s+(SEQ_[0-9A-Fa-f]+)',
                      seq_path.read_text(errors='replace'))
    return found.group(1) if found else None


def explain(exc):
    """Turn an interpreter/baker failure into something a human can act on.

    The shared interpreter hard-fails on anything it has no SCSP counterpart
    for rather than silently producing wrong music, so about half the 105
    sequences cannot be baked yet. Say which wall was hit instead of showing a
    traceback: the fix is to teach build_title_audio.py the opcode, which is
    real work and a deliberate decision, not something this tool should guess.
    """
    text = str(exc)
    op = re.search(r'Unsupported (\w+) opcode: (\w+)', text)
    if op:
        return ('Not supported yet: the %s opcode `%s` has no SCSP counterpart '
                'in shared/tools/build_title_audio.py, so this sequence cannot '
                'be baked without teaching the interpreter that opcode.'
                % (op.group(1), op.group(2)))
    if 'Infinite release' in text:
        return ('Not supported yet: this soundfont asks for an infinite '
                'envelope release, which the SCSP player has no equivalent for.')
    if 'RangeLo' in text or 'SampleLo' in text:
        return ('Not supported yet: this soundfont has split-range instruments '
                '(a different sample above and below a key), which the baker '
                'does not handle. Try another soundfont id.')
    if isinstance(exc, KeyError):
        return ('Soundfont mismatch: this sequence wants an instrument or '
                'envelope field the loader does not provide (%s). Try another '
                'soundfont id.' % text)
    return 'Cannot bake this sequence: %s' % (text or type(exc).__name__)


def probe(source, sequence, **overrides):
    """Can this sequence be baked? Returns (built, None) or (None, reason)."""
    try:
        return render(source, sequence, **overrides), None
    except Exception as exc:
        return None, explain(exc)


def catalog(source=None, root=ROOT):
    """Every sequence in the extraction, header-read only -- no interpreting."""
    if source is None:
        source, error = find_source(root)
        if source is None:
            raise ValueError(error)
    names = sequence_names(root)
    usage = dict(IN_GAME)
    for track in cdda_tracks(root):
        usage[track['sequence']] = 'CD: %s (track %d)' % (track['name'], track['track'])
    entries = []
    for path in sorted((source / 'sequences').glob('seq_*.seq'),
                       key=lambda p: int(re.search(r'seq_(\d+)', p.name)[1])):
        number = int(re.search(r'seq_(\d+)', path.name)[1])
        try:
            font, loop = soundfont_of(path), loop_label_of(path)
            error = None if font is not None else 'declares no soundfont'
        except OSError as exc:
            font, loop, error = None, None, str(exc)
        entries.append(dict(id=str(number), sequence=number, path=path,
                            name=names.get(number, 'seq_%d' % number),
                            soundfont=font, loop=loop, bytes=path.stat().st_size,
                            in_game=usage.get(number), error=error))
    return entries


def survey(source, entries=None, progress=None):
    """Try every sequence and say which ones bake, for the whole catalog.

    Slow -- it interprets and bakes each sequence -- so it is an explicit
    action rather than something the catalog does on open.
    """
    entries = entries if entries is not None else catalog(source)
    rows = []
    for index, entry in enumerate(entries):
        if progress:
            progress(index, len(entries), entry)
        built, reason = probe(source, entry['sequence'])
        rows.append(dict(entry, bakes=built is not None, reason=reason,
                         seconds=built['seconds'] if built else None))
    return rows


def render(source, sequence, soundfont=None, loop=None, stop_at_loop=None,
           budget=None, voices=None):
    """Interpret and bake one sequence. The shared work behind inspect and bake.

    Every argument but the sequence is an override of what the sequence itself
    declares, so the default path matches what the shipping builders produce.
    """
    seq = Path(source) / ('sequences/seq_%d.seq' % sequence)
    if not seq.is_file():
        raise ValueError('missing sequence: %s' % seq)
    font_id = soundfont if soundfont is not None else soundfont_of(seq)
    if font_id is None:
        raise ValueError('seq %d declares no soundfont; choose one' % sequence)
    if loop is None:
        loop = loop_label_of(seq)
    if stop_at_loop is None:
        stop_at_loop = loop is not None

    # The builders set these as module attributes rather than arguments; match
    # that, and restore them so one bake cannot leak its budget into the next.
    saved = audio.MUSIC_SAMPLE_BUDGET, audio.VOICES
    try:
        if budget:
            audio.MUSIC_SAMPLE_BUDGET = int(budget)
        if voices:
            audio.VOICES = int(voices)
        notes, tempo, volumes, gain, intro, end, omitted = audio.interpret(
            seq, loop or 'SEQ_0000', stop_at_loop=stop_at_loop)
        times = audio.timeline(tempo, end)
        envelopes, instruments, samples, pcm, hashes = audio.load_font(
            Path(source), font_id)
        # Soundfont drum ranges select the sample/envelope/pan by the note key.
        font = ET.parse(Path(source) / ('soundfonts/Soundfont_%d.xml' % font_id))
        found = font.getroot().find('Drums')
        drums = [] if found is None else list(found)
        for note in notes:
            if note['program'] != 'FONTANY_INSTR_DRUM':
                continue
            selected = next((d.attrib for d in drums
                             if audio.pitch(d.attrib['NoteStart']) <= note['key']
                             <= audio.pitch(d.attrib['NoteEnd'])), None)
            if selected is None:
                raise ValueError('No drum for key %d' % note['key'])
            program = 'drum_' + selected['Name']
            instruments[program] = selected
            note['program'] = program
            note['pan'] = int(selected['Pan'])
        frames, levels, triggers, cooked = audio.bake(
            notes, times, volumes, gain, envelopes, instruments, samples, end,
            limit_one_shots=True, steal_releasing=True)
        return dict(sequence=sequence, soundfont=font_id, loop=loop,
                    stop_at_loop=stop_at_loop, seq_path=seq,
                    notes=notes, times=times, intro=intro, end=end,
                    omitted=sorted(omitted), samples=samples, pcm=pcm,
                    frames=frames, levels=levels, triggers=triggers,
                    cooked=cooked, seconds=times[end],
                    budget=audio.MUSIC_SAMPLE_BUDGET, voices=audio.VOICES,
                    sample_base=audio.SAMPLE_BASE)
    finally:
        audio.MUSIC_SAMPLE_BUDGET, audio.VOICES = saved


def report(built):
    """A human summary of a render, with the limits it has to live inside."""
    peak = 0
    if built['frames']:
        voices, levels = built['voices'], built['levels']
        peak = max(sum(1 for v in range(voices) if levels[f * voices + v] != 255)
                   for f in range(built['frames']))
    return dict(
        sequence=built['sequence'], soundfont=built['soundfont'],
        loop=built['loop'] or 'from the top', seconds=built['seconds'],
        frames=built['frames'], notes=len(built['notes']),
        triggers=len(built['triggers']), pcm_bytes=len(built['pcm']),
        level_bytes=len(built['levels']), peak_voices=peak,
        voices=built['voices'],
        # load_font resamples the samples down to fit the budget and then adds
        # 4 guard samples to each so SCSP interpolation cannot read into the
        # next instrument. Those guards, and per-sample rounding, sit on top of
        # the budget, so a normal bank lands slightly above budget*2. Only a
        # real overrun matters, and it is reported rather than corrected here.
        sample_budget_bytes=built['budget'] * 2,
        over_sample_budget=len(built['pcm']) > built['budget'] * 2
                                               + 10 * len(built['samples']),
        frames_fit=0 < built['frames'] <= 65535,
        omitted=built['omitted'])


def summary(built):
    """The report as the lines the GUI shows."""
    r = report(built)
    lines = [
        'Sequence %d  soundfont %d  loop %s' % (r['sequence'], r['soundfont'],
                                                r['loop']),
        '%.1f s  %d frames  %d notes  %d triggers'
        % (r['seconds'], r['frames'], r['notes'], r['triggers']),
        'PCM %d bytes of %d budget%s'
        % (r['pcm_bytes'], r['sample_budget_bytes'],
           '  OVER BUDGET' if r['over_sample_budget'] else ''),
        'Levels %d bytes  peak %d of %d voices'
        % (r['level_bytes'], r['peak_voices'], r['voices']),
    ]
    if not r['frames_fit']:
        lines.append('Score does not fit the player 16-bit frame count.')
    if r['omitted']:
        lines.append('No SCSP counterpart, dropped: ' + ', '.join(r['omitted']))
    return '\n'.join(lines)


def score_header(name, built, loop_frame):
    """The same generated header shape the shipping builders emit."""
    lower = name.lower()
    out = ['/* Generated by tools/music-workshop from US 1.2. */',
           '#ifndef %s_SCORE_H' % name, '#define %s_SCORE_H' % name,
           '#include <stdint.h>',
           '#define %s_VOICES %d' % (name, built['voices']),
           '#define %s_FRAMES %d' % (name, built['frames']),
           '#define %s_LOOP_FRAME %d' % (name, loop_frame),
           '#define %s_SAMPLE_BASE %d' % (name, built['sample_base']),
           '#define %s_PCM_BYTES %d' % (name, len(built['pcm'])),
           '#define %s_LEVEL_BYTES %d' % (name, len(built['levels'])),
           '#define %s_TRIGGER_COUNT %d' % (name, len(built['triggers'])),
           'typedef struct { uint32_t offset; uint16_t loop_start, loop_end; }'
           ' %s_pcm_t;' % lower,
           'typedef struct { uint16_t frame; uint8_t slot, sample;'
           ' uint16_t pitch; uint8_t pan; } %s_trigger_t;' % lower,
           'static const %s_pcm_t %s_pcm[] = {' % (lower, lower)]
    out += ['    { %d, %d, %d },' % (s['offset'], s['loop_start'], s['loop_end'])
            for s in built['samples']]
    out += ['};', 'static const %s_trigger_t %s_triggers[] = {' % (lower, lower)]
    out += ['    { %d, %d, %d, %d, %d },' % t for t in built['triggers']]
    out += ['};', '#endif', '']
    return '\n'.join(out)


def revision(name, workspace=WORKSPACE):
    folder = (Path(workspace) / name
              / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-'
                 + uuid.uuid4().hex[:8]))
    folder.mkdir(parents=True)
    return folder


def bake(source, sequence, name, workspace=WORKSPACE, preserve_intro=False,
         preview_seconds=80, built=None, **overrides):
    """Write one Saturn music bank into a fresh workspace revision folder.

    Writes PCM, levels, a score header, a manifest and optional WAV preview.
    Default destination is the workspace; installation uses a staging folder.
    """
    name = re.sub(r'[^A-Za-z0-9_]', '_', name).strip('_').upper()
    if not name:
        raise ValueError('Give the bank a name')
    if built is None:
        built = render(source, sequence, **overrides)
    loop_frame = (round(built['times'][built['intro']] * audio.FPS)
                  if preserve_intro else 0)

    folder = revision(name, workspace)
    (folder / (name + '_PCM.RAW')).write_bytes(built['pcm'])
    (folder / (name + '_LEVELS.RAW')).write_bytes(built['levels'])
    (folder / ('%s_score.h' % name.lower())).write_text(
        score_header(name, built, loop_frame))

    peak = None
    if preview_seconds:
        peak = audio.preview(folder / 'preview.wav', preview_seconds,
                             built['frames'], built['levels'], built['cooked'],
                             built['samples'])

    manifest = dict(version='ntsc-1.2 US', tool='tools/music-workshop',
                    name=name, source=str(source), loop_frame=loop_frame,
                    preview_peak=peak,
                    sequence_sha256=hashlib.sha256(
                        built['seq_path'].read_bytes()).hexdigest(),
                    **report(built))
    manifest['limitations'] = [
        ('Source sequence intro/loop point preserved' if preserve_intro else
         'Loops from the top; no musical loop point was requested'),
        'No N64 reverb or vibrato',
        'PCM resampled to fit SCSP RAM',
        '60 Hz envelopes and quantized SCSP pitch/pan',
        '%d SCSP voices; quietest releasing voice reclaimed at saturation'
        % built['voices'],
        'Host bake and host WAV preview, not target playback verification',
        'Written to the workspace only; no game asset was changed']
    (folder / ('%s_manifest.json' % name.lower())).write_text(
        json.dumps(manifest, indent=2, default=str) + '\n')
    return folder


CDDA_TARGET = 'CD-DA track (Red Book)'
CDDA_MANIFEST = 'game/assets/audio/cdda_tracks.json'

sys.path.insert(0, str(ROOT / 'game/tools'))
import song_dictionary


def game_songs(root=ROOT):
    return song_dictionary.load(Path(root) / 'game')['songs']


def assign_song(song, source, target, root=ROOT):
    """Update one stable song route; no rendering or physical track literals."""
    path = Path(root) / 'game/assets/audio/songs.json'
    document = song_dictionary.load(Path(root) / 'game')
    entry = next((s for s in document['songs'] if s['song'] == song), None)
    if entry is None:
        raise ValueError('Choose a defined game song')
    entry.pop('bank', None)
    entry.pop('cd', None)
    entry['src'] = source
    entry['cd' if source == 'CD' else 'bank'] = target
    song_dictionary.validate(document, cdda_tracks(root))
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(document, indent=2) + '\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def cdda_tracks(root=ROOT):
    """The Red Book track list the disc is built from."""
    path = Path(root) / CDDA_MANIFEST
    if not path.is_file():
        return []
    return sorted(json.loads(path.read_text())['tracks'],
                  key=lambda e: e['track'])


def install_cdda_track(sequence, name, soundfont=None, note=None, root=ROOT,
                       source=None):
    """Add or replace a Red Book track, then render every track and the header.

    The track list is data (assets/audio/cdda_tracks.json). Adding to it is all
    that is needed for the new track to reach the disc and be playable: the cue
    writer already walks TRACKnn.BIN in order, and cdda_play accepts any track
    between the generated CDDA_TRACK_FIRST and CDDA_TRACK_LAST.

    Rendering is delegated to game/tools/build_cdda.py so the CD renderer is not
    duplicated here, and so a bad entry fails before anything is handed to the
    build.
    """
    key = re.sub(r'[^A-Za-z0-9_]', '_', name or '').strip('_').upper()
    if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', key) or key in ('FIRST', 'LAST', 'COUNT'):
        raise ValueError('Give the track a name; it becomes CDDA_TRACK_<NAME>')
    if soundfont is None:
        soundfont = soundfont_of(
            Path(source) / ('sequences/seq_%d.seq' % sequence)) if source else None
    if soundfont is None:
        raise ValueError('Choose a soundfont for the CD track')

    path = Path(root) / CDDA_MANIFEST
    document = json.loads(path.read_text())
    tracks = sorted(document['tracks'], key=lambda e: e['track'])
    entry = dict(name=key, sequence=int(sequence), soundfont=int(soundfont),
                 note=note or 'sequence %d, added by tools/music-workshop'
                 % sequence)
    existing = next((e for e in tracks if e['name'].upper() == key), None)
    if existing:                       # Replace a track rather than duplicate it.
        entry['track'] = existing['track']
        tracks[tracks.index(existing)] = entry
    else:
        entry['track'] = (tracks[-1]['track'] + 1) if tracks else 2
        if entry['track'] > 99:
            raise ValueError('A disc holds at most 99 tracks')
        tracks.append(entry)

    previous = path.read_bytes()
    document['tracks'] = tracks
    path.write_text(json.dumps(document, indent=2) + '\n')
    try:
        command = [sys.executable, str(ROOT / 'game/tools/build_cdda.py'),
                   '--manifest', str(path), '--out', str(Path(root) / 'game/build'),
                   '--header', str(Path(root) / 'game/build/generated/cdda_tracks.h')]
        if source:
            command += ['--source', str(source)]
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode:
            raise ValueError('build_cdda.py failed:\n'
                             + (done.stderr or done.stdout).strip())
    except Exception:
        path.write_bytes(previous)     # Never leave a manifest the build rejects.
        raise
    return entry


def publish_song(source, song, target, sequence, name='', soundfont=None,
                 built=None, preserve_intro=False, root=ROOT):
    """Stage audio and its route together, then replace with rollback on write failure."""
    root = Path(root).resolve()
    document = song_dictionary.load(root / 'game')
    tracks = cdda_tracks(root)
    route = next((s for s in document['songs'] if s['song'] == song), None)
    if route is None:
        raise ValueError('Choose a defined game song before publishing')
    if target == CDDA_TARGET:
        key = re.sub(r'[^A-Za-z0-9_]', '_', name or '').strip('_').upper()
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', key) or key in ('FIRST', 'LAST', 'COUNT'):
            raise ValueError('Give the CD song a valid name')
        kind = 'CD'
        tracks = tracks + [dict(name=key)]
    elif target in GAME_TARGETS:
        kind, key = 'BANK', GAME_TARGETS[target][1].lower()
        if built is None:
            raise ValueError('Publish requires a baked sound bank')
    else:
        raise ValueError('Choose a game destination before publishing')
    route.pop('bank', None)
    route.pop('cd', None)
    route.update(src=kind)
    route['cd' if kind == 'CD' else 'bank'] = key
    # Reject unsuitable streaming/CD routes before rendering or touching assets.
    song_dictionary.validate(document, tracks)
    with tempfile.TemporaryDirectory(prefix='.music-publish-', dir=root) as temp:
        stage = Path(temp)
        manifest = stage / CDDA_MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes((root / CDDA_MANIFEST).read_bytes())
        if kind == 'CD':
            # Reuse verified render caches while keeping all writes isolated.
            for track in cdda_tracks(root):
                for suffix in ('.BIN', '.json'):
                    relative = Path('game/build') / ('TRACK%02d%s' % (track['track'], suffix))
                    original = root / relative
                    if original.is_file():
                        (stage / relative).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(original, stage / relative)
            install_cdda_track(sequence, name, soundfont=soundfont, root=stage, source=source)
        else:
            install_game_bank(source, built, target, preserve_intro, root=stage)
        (stage / 'game/assets/audio/songs.json').write_text(json.dumps(document, indent=2) + '\n')
        # Song mapping last, after all audio and the CD declaration exist.
        files = sorted((p for p in stage.rglob('*') if p.is_file()),
                       key=lambda p: (p.name == 'songs.json', str(p)))
        previous, changed = {}, []
        try:
            for staged in files:
                dest = root / staged.relative_to(stage)
                old = dest.read_bytes() if dest.exists() else None
                if old == staged.read_bytes():
                    continue
                previous[dest] = old
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, dest)
                changed.append(dest)
        except OSError:
            for dest in reversed(changed):
                if previous[dest] is None:
                    dest.unlink(missing_ok=True)
                else:
                    dest.write_bytes(previous[dest])
            raise
    return root / 'game/assets/audio/songs.json'


def install_game_bank(source, built, target, preserve_intro=False, root=ROOT):
    """Replace one named source bank; generation/validation precedes overwrites."""
    if target not in GAME_TARGETS:
        raise ValueError('Choose an existing game music target')
    folder, prefix, raw = GAME_TARGETS[target]
    if not 1 <= built['voices'] <= 24:
        raise ValueError('Game music needs 1..24 voices; remaining slots belong to SFX')
    if not 0 < built['frames'] <= 65535:
        raise ValueError('Score does not fit the player 16-bit frame count')
    if built['sample_base'] < 0x1000 or built['sample_base'] + len(built['pcm']) > 0x50000:
        raise ValueError('Music PCM does not fit below the game SFX boundary (0x50000)')
    if len(built['levels']) != built['frames'] * built['voices']:
        raise ValueError('Envelope size does not match frames and voices')
    if report(built)['over_sample_budget']:
        raise ValueError('Music PCM exceeds the selected sample budget')
    destination = Path(root) / folder
    destination.mkdir(parents=True, exist_ok=True)
    # Stage beside the destination for same-volume replace. No workspace export
    # or WAV is needed to install a source bank into the game.
    with tempfile.TemporaryDirectory(prefix='.music-bank-', dir=destination) as temp:
        revision_folder = bake(source, built['sequence'], prefix, workspace=temp,
                               preserve_intro=preserve_intro, preview_seconds=0, built=built)
        manifest_path = revision_folder / (prefix.lower() + '_manifest.json')
        manifest = json.loads(manifest_path.read_text())
        manifest['game_target'] = target
        manifest['limitations'][-1] = 'Installed game source bank; rebuild Clean to update the disc'
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        names = {prefix + '_PCM.RAW': raw + '_PCM.RAW',
                 prefix + '_LEVELS.RAW': raw + '_LEVELS.RAW',
                 prefix.lower() + '_score.h': prefix.lower() + '_score.h',
                 prefix.lower() + '_manifest.json': prefix.lower() + '_manifest.json'}
        previous = {name: (destination / name).read_bytes()
                    if (destination / name).exists() else None for name in names.values()}
        replaced = []
        try:
            for source_name, dest_name in names.items():
                os.replace(revision_folder / source_name, destination / dest_name)
                replaced.append(dest_name)
        except OSError:
            for name in reversed(replaced):
                path = destination / name
                if previous[name] is None:
                    path.unlink()
                else:
                    restore = Path(temp) / name
                    restore.write_bytes(previous[name])
                    os.replace(restore, path)
            raise
    return destination
