"""Read OoT's message table into pages, lines and coloured runs.

Shared by build_dialogue.py (NPC conversations) and build_cutscenes.py (the
opening's narration), so the one understanding of the message format lives in
one place.

The extracted table keeps the original's control macros as plain text:

    UNSKIPPABLE "Oh, " COLOR(LIGHTBLUE) "Navi the fairy" COLOR(DEFAULT) "...\\n"
    "Listen to my words, the words of \\n"
    "the " COLOR(RED) "Deku Tree" COLOR(DEFAULT) "..."
    BOX_BREAK

so colour is a run *inside* a line, not a property of the line. A line becomes
a list of (text, colour) runs; a line with no COLOR macro is a single default
run, which is the ordinary case.

What is honoured and what is not:

  * COLOR      -> a run colour, mapped to the Saturn text palette.
  * BOX_BREAK  -> a page boundary; the player waits for A.
  * BOX_BREAK_DELAYED(n) -> a page boundary that advances itself after n
                    cutscene ticks. The opening's narration depends on it.
  * FADE(n)    -> the message fades out by itself after n ticks, with no
                    button press. The last narration page ends this way.
  * SHIFT(n)   -> a horizontal offset in half-characters. Kept as a column
                    offset, since the narration is centred with it.
  * NAME       -> the player's name, spliced in before the literals are read.
  * Everything else (icons, speed, sound, ocarina) is dropped: none of it
    survives to a 40-column VDP2 text layer, and half-honouring it would be
    worse than leaving it out.
"""
import re

# OoT colour name -> Jo text palette index (jo/colors.h:45-51).
#
# LIGHTBLUE is the one that matters for the opening -- it is Navi's colour --
# and Jo has no light blue, so it takes the Blue slot and that palette entry is
# recoloured to match. PINK likewise has no exact slot; Purple is the closest.
COLOURS = {
    'DEFAULT':   'WHITE',
    'WHITE':     'WHITE',
    'BLACK':     'BLACK',
    'RED':       'RED',
    'GREEN':     'GREEN',
    'BLUE':      'BLUE',
    'LIGHTBLUE': 'BLUE',
    'YELLOW':    'YELLOW',
    'PINK':      'PURPLE',
    'PURPLE':    'PURPLE',
    # Used by a handful of messages for a value the game fills in.
    'ADJUSTABLE': 'WHITE',
}

DEFAULT_COLOUR = 'WHITE'

# Width of OoT's message text field in pixels. SHIFT offsets are pixels into
# it (z_message.c:1485), so this is what turns one into a column.
MESSAGE_FIELD_PIXELS = 256

# One token of a message body: a quoted literal, or a macro we care about.
TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"'
                   r'|COLOR\(\s*(\w+)\s*\)'
                   r'|SHIFT\(\s*(\d+)\s*\)'
                   r'|(BOX_BREAK_DELAYED)\(\s*(\d+)\s*\)'
                   r'|(BOX_BREAK)\b'
                   r'|FADE\(\s*(\d+)\s*\)')


def msg_groups(block):
    """The MSG(...) bodies of one DEFINE_MESSAGE, by balanced parentheses.

    A regex cannot do this: message bodies contain their own parenthesised
    macros, and the last one is often FADE(n) or SHIFT(n) right before the
    closing paren. Scanning for the first ')' truncates those messages and
    silently drops whatever followed -- including the FADE that ends the
    opening narration.
    """
    groups, at = [], 0
    while True:
        start = block.find('MSG(', at)
        if start < 0:
            return groups
        depth, i = 1, start + 4
        while depth and i < len(block):
            if block[i] == '(':
                depth += 1
            elif block[i] == ')':
                depth -= 1
            i += 1
        groups.append(block[start + 4:i - 1])
        at = i


def load_messages(oot):
    """Every message's English body and box type, keyed by text id."""
    path = oot / 'extracted/ntsc-1.2/text/message_data.h'
    if not path.is_file():
        raise SystemExit('extracted message table not found: %s' % path)
    raw = path.read_text(encoding='utf-8', errors='replace')
    messages = {}
    for block in re.split(r'(?=DEFINE_MESSAGE\()', raw):
        head = re.match(r'DEFINE_MESSAGE\((0x[0-9A-Fa-f]{4}),\s*(\w+),\s*(\w+)',
                        block)
        if not head:
            continue
        # MSG(...) groups are jpn, nes, ger, fra in that order; take the NES one.
        groups = msg_groups(block)
        if len(groups) < 2:
            continue
        messages[int(head.group(1), 16)] = dict(
            body=groups[1], box=head.group(2), position=head.group(3))
    return messages


def parse_pages(body, max_lines=4, max_columns=38, max_pages=16):
    """One message body -> a list of pages.

    Each page is {'lines': [[(text, colour), ...], ...], 'advance': ...,
    'delay': n}. `advance` is 'button' (wait for A), 'delay' (auto after
    `delay` ticks) or 'fade' (fade out after `delay` ticks).
    """
    if not body or 'MISSING' in body:
        return []

    # NAME is a macro OUTSIDE the quotes -- the player's name spliced into the
    # sentence -- so it is substituted before the literals are gathered, or the
    # sentence loses its subject.
    body = re.sub(r'\bNAME\b', '"Link"', body)

    pages = []
    page = _new_page()
    colour = DEFAULT_COLOUR
    shift = 0

    for match in TOKEN.finditer(body):
        literal, set_colour, set_shift, delayed, delay, box_break, fade = \
            match.groups()
        if literal is not None:
            colour = _append(page, literal, colour, shift)
            shift = 0
        elif set_colour is not None:
            colour = COLOURS.get(set_colour, DEFAULT_COLOUR)
        elif set_shift is not None:
            # SHIFT is a pixel offset: z_message.c:1485 does textPosX += n.
            # Kept in pixels here and scaled to columns in _trim, which is the
            # only place that knows how wide the box is.
            shift = int(set_shift)
        elif delayed is not None:
            page['advance'] = 'delay'
            page['delay'] = int(delay)
            pages, page, colour = _finish(pages, page)
        elif box_break is not None:
            pages, page, colour = _finish(pages, page)
        elif fade is not None:
            page['advance'] = 'fade'
            page['delay'] = int(fade)

    _finish(pages, page)
    return [_trim(p, max_lines, max_columns) for p in pages[:max_pages]]


def _new_page():
    return dict(lines=[_new_line()], advance='button', delay=0)


def _new_line():
    """A line is its coloured runs plus the column it starts at.

    The indent is kept separate from the runs so trimming cannot eat it: the
    narration is centred with SHIFT, and stripping that padding as ordinary
    leading whitespace would left-align the whole opening.
    """
    return dict(runs=[], indent=0)


def _append(page, literal, colour, shift):
    """Add one quoted literal's text to the page, splitting on newlines."""
    text = literal.replace('\\n', '\n')
    # Control bytes and the table's own escapes are not printable text.
    text = re.sub(r'\\[0-9A-Fa-fx]+', '', text)
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    for index, part in enumerate(text.split('\n')):
        if index:
            page['lines'].append(_new_line())
        line = page['lines'][-1]
        if shift and not line['runs']:
            line['indent'] = shift
            shift = 0
        if part:
            line['runs'].append((part, colour))
    return colour


def _finish(pages, page):
    if any(line['runs'] for line in page['lines']):
        pages.append(page)
    return pages, _new_page(), DEFAULT_COLOUR


def _trim(page, max_lines, max_columns):
    """Drop empty lines, collapse runs of spaces and clip to the box."""
    lines = []
    for line in page['lines']:
        # The original's SHIFT is a pixel offset into a text field about
        # MESSAGE_FIELD_PIXELS wide; scale it to this box's columns. This is
        # an approximation -- OoT's font is proportional and ours is not -- so
        # a centred line lands close to centre rather than exactly on it.
        indent = line['indent'] * max_columns // MESSAGE_FIELD_PIXELS
        indent = min(indent, max(0, max_columns - 1))
        trimmed, width = [], indent
        for text, colour in line['runs']:
            # Collapse the original's alignment padding, but keep a single
            # space so words never run together.
            text = re.sub(r'\s+', ' ', text)
            if not trimmed:
                text = text.lstrip()
            if not text:
                continue
            if width + len(text) > max_columns:
                text = text[:max_columns - width]
            if text:
                trimmed.append((text, colour))
                width += len(text)
            if width >= max_columns:
                break
        if trimmed:
            # Trailing space on the last run reads as a ragged edge.
            text, colour = trimmed[-1]
            trimmed[-1] = (text.rstrip(), colour)
            if not trimmed[-1][0]:
                trimmed.pop()
        if trimmed:
            lines.append(dict(runs=trimmed, indent=indent))
    page = dict(page)
    page['lines'] = lines[:max_lines]
    return page


def plain(page):
    """A page's lines as plain strings, for callers with no colour support."""
    return [' ' * line['indent'] + ''.join(text for text, _ in line['runs'])
            for line in page['lines']]
