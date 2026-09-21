#!/usr/bin/env python
"""Extract the Kokiri speakers' real US 1.2 dialogue into Saturn text pages.

Nothing here is written by hand. Three things come straight out of the decomp:

  * WHICH line each speaker says -- and, now, under WHICH CONDITIONS. Each
    actor's text-id function is a ladder of guarded returns; this tool parses
    the whole ladder and emits it as an ordered rule list the runtime evaluates
    against save_state.c. Previously only one constant per speaker was taken,
    which is why Mido shipped saying 0x1045 -- his post-Kokiri-Emerald line --
    on a fresh file. Source functions:
        EnKo_GetTextIdChild        ovl_En_Ko/z_en_ko.c
        EnMd_GetTextIdKokiriForest ovl_En_Md/z_en_md.c
        EnSa_GetTextId             ovl_En_Sa/z_en_sa.c
  * The ENGLISH text -- assets/text/message_data.h, the NES message of each
    DEFINE_MESSAGE, which is the US script.
  * Page breaks -- BOX_BREAK in that same message, so a conversation keeps the
    original's pagination instead of a re-wrap invented here.

Flag numbers are resolved from include/save.h and include/item.h, never typed
in. A condition shape the parser does not recognise is a hard error: a guard
silently dropped would reintroduce exactly the bug this rewrite fixes.

If a speaker's text is missing from the decomp the entry is emitted as an
explicitly authored placeholder and counted in the report, so an invented line
can never be mistaken for the original script.
"""

import argparse
import pathlib
import re
import sys

MAX_PAGES = 4
MAX_LINES = 4
MAX_COLUMNS = 34

SPEAKER_NAMES = {'CHILD': 'Kokiri', 'MIDO': 'Mido', 'SARIA': 'Saria'}

# Condition kinds shared with the runtime (dialogue_cond_t.kind).
COND_EVENT = 0      # GET_EVENTCHKINF(flag)
COND_INFTABLE = 1   # GET_INFTABLE(flag)
COND_QUEST = 2      # CHECK_QUEST_ITEM(bit)
COND_EQUIP = 3      # CUR_EQUIP_VALUE(type) == value
COND_ITEMGET = 4    # GET_ITEMGETINF(flag)

COND_NAMES = {COND_EVENT: 'EVENT', COND_INFTABLE: 'INFTABLE',
              COND_QUEST: 'QUEST', COND_EQUIP: 'EQUIP',
              COND_ITEMGET: 'ITEMGET'}


class Unsupported(Exception):
    """A source shape the parser refuses to guess at."""


# ---------------------------------------------------------------------------
# symbol table
# ---------------------------------------------------------------------------

def load_symbols(oot):
    """Every flag/quest/equip constant we may meet, name -> integer.

    save.h carries the flag numbers as #defines; item.h carries the quest bits
    and equipment enums as commented enumerators (`/* 0x12 */ QUEST_...`).
    """
    symbols = {}
    save_h = oot / 'include/save.h'
    if not save_h.is_file():
        sys.exit('decomp include/save.h not found: %s' % save_h)
    for name, value in re.findall(
            r'^#define\s+((?:EVENTCHKINF|INFTABLE|ITEMGETINF)_[A-Z0-9_]+)'
            r'\s+(0x[0-9A-Fa-f]+|\d+)\s*$', save_h.read_text(
                encoding='utf-8', errors='replace'), re.M):
        symbols[name] = int(value, 0)
    item_h = oot / 'include/item.h'
    if not item_h.is_file():
        sys.exit('decomp include/item.h not found: %s' % item_h)
    for value, name in re.findall(
            r'/\*\s*(0x[0-9A-Fa-f]+|\d+)\s*\*/\s*((?:QUEST|EQUIP_TYPE|EQUIP_VALUE)'
            r'_[A-Z0-9_]+)\s*,', item_h.read_text(encoding='utf-8',
                                                  errors='replace')):
        symbols[name] = int(value, 0)
    return symbols


def resolve(symbols, token):
    token = token.strip()
    if re.fullmatch(r'0x[0-9A-Fa-f]+|\d+', token):
        return int(token, 0)
    if token in symbols:
        return symbols[token]
    raise Unsupported('unknown constant %r' % token)


# ---------------------------------------------------------------------------
# C source slicing
# ---------------------------------------------------------------------------

def balanced(text, start, open_ch, close_ch):
    """End index just past the balanced group that begins at `start`."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise Unsupported('unbalanced %s in source' % open_ch)


def function_body(path, name):
    """The brace-delimited body of one function, braces excluded."""
    text = path.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'\b%s\s*\([^)]*\)\s*\{' % re.escape(name), text)
    if not match:
        raise Unsupported('function %s not found in %s' % (name, path.name))
    open_brace = text.index('{', match.start())
    end = balanced(text, open_brace, '{', '}')
    return text[open_brace + 1:end - 1]


def statements(text):
    """Top-level statements of a block, in order.

    Yields either ('if', condition, body, else_body) or ('stmt', source).
    Nested braces and parens are kept together; comments are stripped first.
    """
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text[i] == '{':
            end = balanced(text, i, '{', '}')
            yield ('stmt', text[i:end])
            i = end
            continue
        word = re.match(r'\bif\b', text[i:])
        if word:
            paren = text.index('(', i)
            paren_end = balanced(text, paren, '(', ')')
            condition = text[paren + 1:paren_end - 1]
            body, i = _clause(text, paren_end)
            else_body = None
            rest = text[i:]
            lead = re.match(r'\s*\belse\b', rest)
            if lead:
                else_body, i = _clause(text, i + lead.end())
            yield ('if', condition, body, else_body)
            continue
        end = text.find(';', i)
        if end < 0:
            raise Unsupported('statement without terminator: %r' % text[i:i + 60])
        # A `switch` or loop at this level is not something we model.
        if re.match(r'\b(switch|for|while|do|goto)\b', text[i:]):
            raise Unsupported('control flow not modelled: %r' % text[i:i + 40])
        yield ('stmt', text[i:end + 1])
        i = end + 1


def _clause(text, pos):
    """One `if`/`else` clause starting at pos: a block or a single statement."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos < len(text) and text[pos] == '{':
        end = balanced(text, pos, '{', '}')
        return text[pos + 1:end - 1], end
    end = text.find(';', pos)
    if end < 0:
        raise Unsupported('clause without terminator')
    return text[pos:end + 1], end + 1


# ---------------------------------------------------------------------------
# condition and rule parsing
# ---------------------------------------------------------------------------

def parse_condition(symbols, source):
    """`&&`-joined guards -> list of condition tuples.

    Returns None for the mask-reaction guard (`textId != 0`), which cannot ever
    hold in this slice because masks do not exist here; the caller drops that
    rule and reports it rather than pretending it is unreachable by accident.
    """
    source = source.strip()
    if '||' in source:
        raise Unsupported('disjunction not modelled: %r' % source)
    conditions = []
    for term in _split_and(source):
        term = term.strip()
        while term.startswith('(') and balanced(term, 0, '(', ')') == len(term):
            term = term[1:-1].strip()
        expect = 1
        while term.startswith('!'):
            expect ^= 1
            term = term[1:].strip()
        if re.fullmatch(r'textId\s*!=\s*0', term):
            return None
        flag = re.fullmatch(r'(?:GET_EVENTCHKINF|Flags_GetEventChkInf)'
                            r'\s*\(\s*([A-Za-z0-9_]+)\s*\)', term)
        if flag:
            conditions.append((COND_EVENT, resolve(symbols, flag.group(1)), 0,
                               expect))
            continue
        flag = re.fullmatch(r'(?:GET_INFTABLE|Flags_GetInfTable)'
                            r'\s*\(\s*([A-Za-z0-9_]+)\s*\)', term)
        if flag:
            conditions.append((COND_INFTABLE, resolve(symbols, flag.group(1)),
                               0, expect))
            continue
        flag = re.fullmatch(r'(?:GET_ITEMGETINF|Flags_GetItemGetInf)'
                            r'\s*\(\s*([A-Za-z0-9_]+)\s*\)', term)
        if flag:
            conditions.append((COND_ITEMGET, resolve(symbols, flag.group(1)),
                               0, expect))
            continue
        flag = re.fullmatch(r'CHECK_QUEST_ITEM\s*\(\s*([A-Za-z0-9_]+)\s*\)',
                            term)
        if flag:
            conditions.append((COND_QUEST, resolve(symbols, flag.group(1)), 0,
                               expect))
            continue
        # CUR_EQUIP_VALUE(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU.
        # ALL_EQUIP_VALUE is deliberately NOT accepted as an alias: Mido's gate
        # depends on the difference between owned and equipped.
        equip = re.fullmatch(r'CUR_EQUIP_VALUE\s*\(\s*([A-Za-z0-9_]+)\s*\)'
                             r'\s*==\s*([A-Za-z0-9_]+)', term)
        if equip:
            conditions.append((COND_EQUIP, resolve(symbols, equip.group(1)),
                               resolve(symbols, equip.group(2)), expect))
            continue
        raise Unsupported('condition not modelled: %r' % term)
    return conditions


def _split_and(source):
    """Split on top-level `&&`, ignoring anything inside parentheses."""
    parts, depth, start = [], 0, 0
    i = 0
    while i < len(source):
        if source[i] == '(':
            depth += 1
        elif source[i] == ')':
            depth -= 1
        elif depth == 0 and source.startswith('&&', i):
            parts.append(source[start:i])
            i += 2
            start = i
            continue
        i += 1
    parts.append(source[start:])
    return parts


def parse_rules(symbols, body, report):
    """A text-id function body -> ordered [(conditions, text_id)].

    The runtime takes the FIRST rule whose conditions all hold, which is
    exactly what a ladder of early returns does. Because of that, no condition
    ever needs negating: a later rule is only reached when the earlier ones
    did not match.
    """
    rules = []

    def walk(text, conditions):
        for item in statements(text):
            if item[0] == 'if':
                _, condition, then_body, else_body = item
                guard = parse_condition(symbols, condition)
                if guard is None:
                    # Mask reaction: unreachable here. Its body is skipped, and
                    # execution continues, which is what the original does when
                    # no mask is worn.
                    report.append('skipped mask-reaction guard (no masks in '
                                  'this slice)')
                    continue
                walk(then_body, conditions + guard)
                if else_body is not None:
                    walk(else_body, list(conditions))
                continue
            source = item[1].strip()
            if source.startswith('{'):
                walk(source[1:-1], list(conditions))
                continue
            ret = re.fullmatch(r'return\s*(.*?)\s*;', source, re.S)
            if not ret:
                continue        # assignment or call: no bearing on text choice
            expression = ret.group(1).strip()
            ternary = _split_ternary(expression)
            if ternary:
                condition, yes, no = ternary
                guard = parse_condition(symbols, condition)
                if guard is None:
                    raise Unsupported('mask reaction inside a ternary')
                rules.append((conditions + guard, resolve(symbols, yes)))
                rules.append((list(conditions), resolve(symbols, no)))
                continue
            if re.fullmatch(r'0x[0-9A-Fa-f]+|\d+', expression):
                rules.append((list(conditions), int(expression, 0)))
                continue
            if expression == 'textId':
                report.append('skipped `return textId` (mask reaction)')
                continue
            raise Unsupported('return expression not modelled: %r' % expression)

    walk(body, [])
    if not rules:
        raise Unsupported('no text ids found in function body')
    return rules


def _split_ternary(expression):
    """`c ? a : b` split at top level, or None."""
    depth = 0
    question = -1
    for i, ch in enumerate(expression):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch == '?':
            question = i
            break
    if question < 0:
        return None
    depth = 0
    for i in range(question + 1, len(expression)):
        ch = expression[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch == ':':
            return (expression[:question], expression[question + 1:i],
                    expression[i + 1:])
    raise Unsupported('ternary without a colon: %r' % expression)


# ---------------------------------------------------------------------------
# speakers
# ---------------------------------------------------------------------------

def enko_cases(symbols, oot, report):
    """One rule list per ENKO_TYPE, from EnKo_GetTextIdChild's switch."""
    path = oot / 'src/overlays/actors/ovl_En_Ko/z_en_ko.c'
    body = function_body(path, 'EnKo_GetTextIdChild')
    switch = re.search(r'switch\s*\(\s*ENKO_TYPE\s*\)\s*\{', body)
    if not switch:
        raise Unsupported('EnKo_GetTextIdChild no longer switches on ENKO_TYPE')
    open_brace = body.index('{', switch.start())
    inner = body[open_brace + 1:balanced(body, open_brace, '{', '}') - 1]
    cases = {}
    chunks = re.split(r'\bcase\s+', inner)[1:]
    for chunk in chunks:
        label, _, tail = chunk.partition(':')
        label = label.strip()
        # ENKO_TYPE_CHILD_0..11 are the numbered Kokiri. FADO and the other
        # named types belong to other scenes; they are reported, not guessed.
        number = re.fullmatch(r'ENKO_TYPE_CHILD_(\d+)', label)
        if not number:
            report.append('ignored En_Ko case %s (not a numbered forest child)'
                          % label)
            continue
        cases[int(number.group(1))] = parse_rules(symbols, tail, report)
    if not cases:
        raise Unsupported('no ENKO_TYPE_CHILD_n cases found')
    return cases


def speaker_rules(symbols, oot, report):
    """(name, enko_type, rules) for every speaker the forest places."""
    out = []
    for kind, rules in sorted(enko_cases(symbols, oot, report).items()):
        out.append(('CHILD', kind, rules))
    mido = function_body(oot / 'src/overlays/actors/ovl_En_Md/z_en_md.c',
                         'EnMd_GetTextIdKokiriForest')
    out.append(('MIDO', 0, parse_rules(symbols, mido, report)))
    saria = function_body(oot / 'src/overlays/actors/ovl_En_Sa/z_en_sa.c',
                          'EnSa_GetTextId')
    out.append(('SARIA', 0, parse_rules(symbols, saria, report)))
    return out


# ---------------------------------------------------------------------------
# message text
# ---------------------------------------------------------------------------

def load_messages(oot):
    """Every message's English pages, keyed by text id."""
    path = oot / 'extracted/ntsc-1.2/text/message_data.h'
    if not path.is_file():
        sys.exit('extracted message table not found: %s' % path)
    raw = path.read_text(encoding='utf-8', errors='replace')
    messages = {}
    for block in re.split(r'(?=DEFINE_MESSAGE\()', raw):
        head = re.match(r'DEFINE_MESSAGE\((0x[0-9A-Fa-f]{4})', block)
        if not head:
            continue
        # MSG(...) groups are jpn, nes, ger, fra in that order; take the NES one.
        groups = re.findall(r'MSG\((.*?)\)\s*(?:,|\))', block, re.S)
        if len(groups) < 2:
            continue
        messages[int(head.group(1), 16)] = groups[1]
    return messages


def clean_pages(body):
    """Plain ASCII pages and lines from one NES message body.

    Control macros carry colour, shifting, icons and speed; none of them
    survive to a 34-column Saturn box, so they are dropped rather than
    half-honoured. BOX_BREAK is kept because it is the original's own page
    boundary.
    """
    if not body or 'MISSING' in body:
        return []
    pages = []
    for chunk in re.split(r'BOX_BREAK\w*', body):
        # NAME is a macro OUTSIDE the quotes -- the player's name spliced into
        # the sentence -- so it has to be substituted before the quoted
        # literals are gathered, or the sentence loses its subject.
        chunk = re.sub(r'\bNAME\b', '"Link"', chunk)
        # Keep only the quoted string literals, then strip the macros.
        text = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', chunk))
        text = text.replace('\\n', '\n')
        text = re.sub(r'[^\x20-\x7E\n]', '', text)
        lines = []
        for line in text.split('\n'):
            line = ' '.join(line.split())
            if line:
                lines.append(line[:MAX_COLUMNS])
        if lines:
            pages.append(lines[:MAX_LINES])
        if len(pages) >= MAX_PAGES:
            break
    return pages


def escape(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'build/generated')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--verify', action='store_true',
                    help='parse and report only; write nothing')
    args = ap.parse_args()

    symbols = load_symbols(args.oot)
    report = []
    try:
        speakers = speaker_rules(symbols, args.oot, report)
    except Unsupported as error:
        # Refusing here is the point. A guard the parser cannot read would
        # otherwise be dropped, and a dropped guard is how Mido ended up
        # speaking his post-Kokiri-Emerald line on a fresh save.
        sys.exit('build_dialogue: %s\n'
                 'The decomp has a shape this tool does not model. Extend the '
                 'parser; do not fall back to a hardcoded text id.' % error)

    messages = load_messages(args.oot)

    # Flatten to the runtime tables. Conditions and rules are pooled the same
    # way pages and lines already are.
    lines_pool, pages_pool, conds_pool, rules_pool, convos = [], [], [], [], []
    authored = 0
    baseline = []
    for speaker, kind, rules in speakers:
        first_rule = len(rules_pool)
        for conditions, text_id in rules:
            pages = clean_pages(messages.get(text_id))
            if not pages:
                pages = [['(Nothing to say yet.)']]
                authored += 1
            first_page = len(pages_pool)
            for page in pages:
                first_line = len(lines_pool)
                lines_pool.extend(page)
                pages_pool.append((first_line, len(page)))
            first_cond = len(conds_pool)
            conds_pool.extend(conditions)
            rules_pool.append((first_cond, len(conditions), first_page,
                               len(pages), text_id))
        convos.append((speaker, kind, first_rule, len(rules_pool) - first_rule))
        # The unconditional rule is what a fresh file sees; report it so a wrong
        # baseline is visible in the build log instead of only in play.
        fresh = [text_id for conditions, text_id in rules if not conditions]
        baseline.append((speaker, kind, fresh[0] if fresh else None))

    if args.verify:
        print('dialogue: %d speakers, %d rules, %d conditions'
              % (len(convos), len(rules_pool), len(conds_pool)))
        for speaker, kind, text_id in baseline:
            label = '%s%s' % (speaker, '' if speaker != 'CHILD' else ' %d' % kind)
            print('  %-10s fresh-file text 0x%04X' % (label, text_id or 0))
        for note in dict.fromkeys(report):
            print('  note: %s' % note)
        return

    args.out.mkdir(parents=True, exist_ok=True)
    banner = '/* Generated by game/tools/build_dialogue.py -- do not edit. */'

    header = [banner, '', '#ifndef KOKIRI_DIALOGUE_H', '# define KOKIRI_DIALOGUE_H',
              '# include <stdint.h>', '',
              "/* Real US 1.2 script. Each speaker's text-id function is",
              '   extracted as an ordered rule list: the runtime picks the',
              '   FIRST rule whose conditions all hold, which is what the',
              '   original ladder of early returns does. Pages are the',
              "   original's own BOX_BREAK boundaries. */",
              '# define DIALOGUE_CONVO_COUNT %d' % len(convos),
              '# define DIALOGUE_RULE_COUNT  %d' % len(rules_pool),
              '# define DIALOGUE_COND_COUNT  %d' % max(len(conds_pool), 1),
              '# define DIALOGUE_PAGE_COUNT  %d' % len(pages_pool),
              '# define DIALOGUE_LINE_COUNT  %d' % len(lines_pool),
              '# define DIALOGUE_MAX_LINES   %d' % MAX_LINES,
              '# define DIALOGUE_MAX_COLUMNS %d' % MAX_COLUMNS, '',
              '/* dialogue_cond_t.kind */']
    for value, name in sorted(COND_NAMES.items()):
        header.append('# define DIALOGUE_COND_%-9s %d' % (name, value))
    header += ['',
               'typedef struct {',
               '    uint8_t  kind;      /* DIALOGUE_COND_*  */',
               '    uint8_t  expect;    /* 1 = must hold, 0 = must not */',
               '    uint16_t flag;      /* flag number, quest bit or equip type */',
               '    uint16_t value;     /* EQUIP only: required equip value */',
               '} dialogue_cond_t;', '',
               'typedef struct { uint16_t first_line; uint8_t lines; } dialogue_page_t;', '',
               'typedef struct {',
               '    uint16_t first_cond;',
               '    uint8_t  conds;     /* 0 = unconditional fall-through */',
               '    uint16_t first_page;',
               '    uint8_t  pages;',
               '    uint16_t text_id;   /* original message id, for tracing */',
               '} dialogue_rule_t;', '',
               'typedef struct {',
               '    uint8_t  speaker;   /* KOKIRI_NPC_* */',
               '    uint8_t  kind;      /* ENKO_TYPE for children, 0 otherwise */',
               '    uint16_t first_rule;',
               '    uint8_t  rules;',
               '} dialogue_convo_t;', '',
               'extern const char * const      dialogue_lines[DIALOGUE_LINE_COUNT];',
               'extern const dialogue_page_t   dialogue_pages[DIALOGUE_PAGE_COUNT];',
               'extern const dialogue_cond_t   dialogue_conds[DIALOGUE_COND_COUNT];',
               'extern const dialogue_rule_t   dialogue_rules[DIALOGUE_RULE_COUNT];',
               'extern const dialogue_convo_t  dialogue_convos[DIALOGUE_CONVO_COUNT];',
               'extern const char * const      dialogue_speaker_names[3];',
               '#endif', '']
    (args.out / 'kokiri_dialogue.h').write_text('\n'.join(header))

    body = [banner, '', '#include "kokiri_dialogue.h"', '#include "kokiri_actors.h"', '',
            'const char * const dialogue_lines[DIALOGUE_LINE_COUNT] = {']
    body += ['    "%s",' % escape(line) for line in lines_pool]
    body += ['};', '', 'const dialogue_page_t dialogue_pages[DIALOGUE_PAGE_COUNT] = {']
    body += ['    { %d, %d },' % page for page in pages_pool]
    body += ['};', '', 'const dialogue_cond_t dialogue_conds[DIALOGUE_COND_COUNT] = {']
    for kind, flag, value, expect in conds_pool:
        body.append('    { DIALOGUE_COND_%s, %d, 0x%02X, %d },'
                    % (COND_NAMES[kind], expect, flag, value))
    if not conds_pool:
        body.append('    { 0, 0, 0, 0 },')
    body += ['};', '', 'const dialogue_rule_t dialogue_rules[DIALOGUE_RULE_COUNT] = {']
    for first_cond, conds, first_page, pages, text_id in rules_pool:
        body.append('    { %d, %d, %d, %d, 0x%04X },'
                    % (first_cond, conds, first_page, pages, text_id))
    body += ['};', '', 'const dialogue_convo_t dialogue_convos[DIALOGUE_CONVO_COUNT] = {']
    for speaker, kind, first_rule, rules in convos:
        body.append('    { KOKIRI_NPC_%s, %d, %d, %d },'
                    % (speaker, kind, first_rule, rules))
    body += ['};', '', 'const char * const dialogue_speaker_names[3] = {']
    body += ['    "%s",' % SPEAKER_NAMES[name] for name in ('CHILD', 'MIDO', 'SARIA')]
    body += ['};', '', '/* END OF FILE */', '']
    (args.out / 'kokiri_dialogue.c').write_text('\n'.join(body))

    print('dialogue: %d speakers, %d rules, %d conditions, %d pages, %d lines'
          % (len(convos), len(rules_pool), len(conds_pool), len(pages_pool),
             len(lines_pool)))
    for speaker, kind, text_id in baseline:
        label = '%s%s' % (speaker, '' if speaker != 'CHILD' else ' %d' % kind)
        print('  %-10s fresh-file text 0x%04X' % (label, text_id or 0))
    if authored:
        print('  %d rule(s) had no extractable text and use an authored '
              'placeholder' % authored)
    else:
        print('  every rule uses original US 1.2 English text')
    for note in dict.fromkeys(report):
        print('  note: %s' % note)


if __name__ == '__main__':
    main()
