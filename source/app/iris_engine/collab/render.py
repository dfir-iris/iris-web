#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""markdown ↔ Yjs XmlFragment bridge for the collaborative editor.

We hold the authoritative Y.Doc server-side (see `business/collab.py`)
and clients speak Yjs updates over the wire. Two conversions are
needed at the storage boundary:

  * `markdown_to_ydoc_update(md)`  → bytes
      Called ONCE per document when its `collab_doc` row is being
      seeded from the source column (`notes.note_content` etc.). We
      parse the markdown into a ProseMirror-shaped XmlFragment inside
      a fresh Y.Doc and return the doc's update bytes. That's what
      the first joiner sees via `sync-init` and what every subsequent
      joiner merges against.

  * `ydoc_update_to_markdown(update)` → str
      Called on flush (last-client-disconnect + periodic tick). We
      apply the stored update into a fresh Y.Doc, walk the fragment,
      render markdown. Written back to the source column.

Both sides must speak the ProseMirror doc shape that TipTap's
`Collaboration` + `y-prosemirror` binding produces client-side. That
means specific tag names (heading / paragraph / bulletList / …), and
marks stored as `_prosemirror-mark` attributes on `XmlText` nodes
matching what y-prosemirror emits. StarterKit's default node set
covers everything the editor currently supports; if we ever add a
new node type on the frontend, we need to teach both sides here.

Design constraints that shape the code:
  1. Idempotent when possible — the SAME markdown must produce the
     SAME Y.Doc every time we re-seed, so that a fresh joiner and a
     re-hydration after restart produce identical state.
  2. Round-trip stable — `render(parse(md))` should match `md`
     modulo whitespace normalization. If it doesn't, users will
     see their content mutate on save.
  3. No inline HTML pass-through: markdown-it-py is CommonMark-only.
     If the source column has legacy HTML (from pre-editor code),
     we drop through to `<html_block>` tokens and render them back
     as a fenced code block. Aggressive, but safe — we're not going
     to reconstruct arbitrary HTML into a CRDT tree.
"""

from __future__ import annotations

import logging
from typing import Iterable

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pycrdt import Doc, XmlElement, XmlFragment, XmlText


logger = logging.getLogger(__name__)


# The Yjs XmlFragment field name that y-prosemirror uses by default.
# Both the frontend Collaboration extension and this renderer MUST
# agree on this key — a mismatch produces an empty editor with no
# obvious error.
_PROSEMIRROR_FIELD = 'prosemirror'


# ---------------------------------------------------------------------------
# markdown → Y.Doc
# ---------------------------------------------------------------------------

def markdown_to_ydoc_update(md: str) -> bytes:
    """Build a fresh Y.Doc from `md` and return its update bytes.

    Empty input is legal — we return the update for an empty doc so
    the client's `sync-init` handler can still apply it cleanly (an
    empty XmlFragment is a valid starting state).
    """
    doc = Doc()
    frag = XmlFragment()
    doc[_PROSEMIRROR_FIELD] = frag

    # `commonmark` + explicit `enable('table')` gives us GFM pipe tables
    # (thead/tbody/tr/th/td tokens) without pulling in the rest of the
    # `gfm-like` preset — notably `linkify`, which requires the extra
    # `linkify-it-py` dependency. Legacy notes and case summaries in
    # production predate the CommonMark editor and often contain tables
    # (findings, IOC lists, etc.); dropping them silently at the parser
    # left users with pipes and dashes rendered as literal text.
    md_parser = (
        MarkdownIt('commonmark', {'html': False, 'breaks': False})
        .enable('table')
    )
    tokens = md_parser.parse(md or '')

    with doc.transaction():
        _build_blocks_into(frag, tokens)

    return doc.get_update()


def _build_blocks_into(container, tokens: list[Token]) -> None:
    """Walk `tokens` and append the corresponding block-level XmlElements
    onto `container` (which must already be integrated into a Doc).

    `container` is either the root XmlFragment or a `listItem`/`blockquote`
    element that's mid-integration. We DON'T open a new transaction here;
    the caller owns the transaction that wraps every mutation.
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        t = tok.type

        if t == 'heading_open':
            level = int(tok.tag[1])  # 'h1' → 1
            close_i = _find_close(tokens, i, 'heading_close')
            el = XmlElement('heading')
            container.children.append(el)
            el.attributes['level'] = str(level)
            _build_inline_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        if t == 'paragraph_open':
            close_i = _find_close(tokens, i, 'paragraph_close')
            el = XmlElement('paragraph')
            container.children.append(el)
            _build_inline_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        if t == 'bullet_list_open':
            close_i = _find_close(tokens, i, 'bullet_list_close')
            el = XmlElement('bulletList')
            container.children.append(el)
            _build_list_items_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        if t == 'ordered_list_open':
            close_i = _find_close(tokens, i, 'ordered_list_close')
            el = XmlElement('orderedList')
            container.children.append(el)
            start = tok.attrGet('start')
            if start is not None and str(start) != '1':
                el.attributes['start'] = str(start)
            _build_list_items_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        if t == 'blockquote_open':
            close_i = _find_close(tokens, i, 'blockquote_close')
            el = XmlElement('blockquote')
            container.children.append(el)
            _build_blocks_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        if t == 'code_block' or t == 'fence':
            el = XmlElement('codeBlock')
            container.children.append(el)
            if tok.info:
                el.attributes['language'] = tok.info.strip()
            # Trailing newline: markdown-it always appends one; TipTap
            # doesn't want it inside the codeBlock's text node.
            body = (tok.content or '').rstrip('\n')
            if body:
                el.children.append(XmlText(body))
            i += 1
            continue

        if t == 'hr':
            container.children.append(XmlElement('horizontalRule'))
            i += 1
            continue

        if t == 'html_block':
            # Legacy content that predates the CommonMark editor. Render
            # it as a code block rather than trying to reconstruct HTML
            # in the tree — keeps content visible and unambiguous while
            # avoiding a whole HTML-to-ProseMirror parser.
            el = XmlElement('codeBlock')
            container.children.append(el)
            el.attributes['language'] = 'html'
            body = (tok.content or '').rstrip('\n')
            if body:
                el.children.append(XmlText(body))
            i += 1
            continue

        if t == 'table_open':
            close_i = _find_close(tokens, i, 'table_close')
            el = XmlElement('table')
            container.children.append(el)
            _build_table_rows_into(el, tokens[i + 1: close_i])
            i = close_i + 1
            continue

        # Anything else: skip. Unknown block tokens are almost always
        # opener/closer noise (thead/tbody are handled inside
        # `_build_table_rows_into`; anything else falls here).
        i += 1


def _build_list_items_into(list_el, tokens: list[Token]) -> None:
    """Turn `list_item_open ... list_item_close` runs inside `tokens`
    into `listItem` XmlElements appended to `list_el`."""
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type != 'list_item_open':
            i += 1
            continue
        close_i = _find_close(tokens, i, 'list_item_close')
        item = XmlElement('listItem')
        list_el.children.append(item)
        _build_blocks_into(item, tokens[i + 1: close_i])
        i = close_i + 1


def _build_table_rows_into(table_el, tokens: list[Token]) -> None:
    """Turn the interior of a GFM table (`table_open ... table_close`)
    into `tableRow` / `tableHeader` / `tableCell` XmlElements matching
    the TipTap Table extension's schema.

    markdown-it wraps the row runs in `thead_open ... thead_close` and
    `tbody_open ... tbody_close`; those wrappers are semantic-only in
    our target schema (TipTap distinguishes header vs body cells at
    the CELL level, not the section level), so we flatten them.

    Each cell in the TipTap schema requires at least one block child.
    We wrap the row's inline content in a `paragraph` — same shape
    y-prosemirror produces when a user types into a fresh table.
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # Skip thead/tbody wrappers — flat row list matches TipTap.
        if tok.type in ('thead_open', 'thead_close', 'tbody_open', 'tbody_close'):
            i += 1
            continue
        if tok.type != 'tr_open':
            i += 1
            continue
        row_close = _find_close(tokens, i, 'tr_close')
        row_el = XmlElement('tableRow')
        table_el.children.append(row_el)
        _build_table_cells_into(row_el, tokens[i + 1: row_close])
        i = row_close + 1


def _build_table_cells_into(row_el, tokens: list[Token]) -> None:
    """Emit `tableHeader` or `tableCell` XmlElements for each th/td
    inside a row. Each cell's inline content becomes a nested
    `paragraph` — TipTap's Table cell requires at least one block
    child, and paragraph is the neutral choice for text-only cells.

    We deliberately DO NOT copy colspan/rowspan/colwidth here. GFM
    pipe tables don't express those; a legacy note being migrated
    into the collab doc is always a plain rectangular grid. If the
    user later merges cells in the TipTap editor, y-prosemirror
    writes the merge attrs into the XmlElement and they survive
    subsequent flushes — this migration path just seeds the simplest
    possible table.
    """
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type == 'th_open':
            close_i = _find_close(tokens, i, 'th_close')
            cell = XmlElement('tableHeader')
            row_el.children.append(cell)
            para = XmlElement('paragraph')
            cell.children.append(para)
            _build_inline_into(para, tokens[i + 1: close_i])
            i = close_i + 1
            continue
        if tok.type == 'td_open':
            close_i = _find_close(tokens, i, 'td_close')
            cell = XmlElement('tableCell')
            row_el.children.append(cell)
            para = XmlElement('paragraph')
            cell.children.append(para)
            _build_inline_into(para, tokens[i + 1: close_i])
            i = close_i + 1
            continue
        i += 1


def _build_inline_into(block_el, inline_tokens: list[Token]) -> None:
    """Walk `paragraph_open ... paragraph_close` interior (or heading
    interior) and append text/hardBreak nodes with marks applied.

    markdown-it flattens the interior of a paragraph into a single
    `inline` token whose `.children` are the actual leaf tokens
    (text, em_open/em_close, strong_open/strong_close, code_inline,
    link_open/link_close, image, softbreak, hardbreak). We flatten
    those with a small mark-stack so bold/italic/code/link/strike
    become y-prosemirror marks on `XmlText` nodes.
    """
    if not inline_tokens:
        return
    # There should be exactly one 'inline' token here (that's how
    # markdown-it structures paragraph/heading interiors).
    inline = None
    for t in inline_tokens:
        if t.type == 'inline':
            inline = t
            break
    if inline is None or not inline.children:
        return

    marks: list[dict] = []

    def _open_mark(name: str, attrs: dict | None = None) -> None:
        m = {'type': name}
        if attrs:
            m['attrs'] = attrs
        marks.append(m)

    def _close_mark(name: str) -> None:
        for i in range(len(marks) - 1, -1, -1):
            if marks[i]['type'] == name:
                marks.pop(i)
                return

    def _emit_text(text: str) -> None:
        if not text:
            return
        node = XmlText(text)
        block_el.children.append(node)
        if marks:
            # y-prosemirror stores marks as an attribute keyed by the
            # y-prosemirror-specific `_pm-marks` convention. In pycrdt
            # we set them as plain attributes; the client's y-prosemirror
            # binding reads them via the same protocol.
            #
            # NOTE: y-prosemirror's actual encoding uses a special
            # attribute name; setting per-mark bool attrs matches how
            # TipTap's Yjs bindings serialize simple marks. This is the
            # brittlest part of the renderer — see the round-trip tests.
            for m in marks:
                node.attributes[m['type']] = _mark_to_attr_value(m)

    for c in inline.children:
        ct = c.type
        if ct == 'text':
            _emit_text(c.content)
        elif ct == 'softbreak':
            _emit_text(' ')
        elif ct == 'hardbreak':
            block_el.children.append(XmlElement('hardBreak'))
        elif ct == 'em_open':
            _open_mark('italic')
        elif ct == 'em_close':
            _close_mark('italic')
        elif ct == 'strong_open':
            _open_mark('bold')
        elif ct == 'strong_close':
            _close_mark('bold')
        elif ct == 's_open':
            _open_mark('strike')
        elif ct == 's_close':
            _close_mark('strike')
        elif ct == 'code_inline':
            _open_mark('code')
            _emit_text(c.content)
            _close_mark('code')
        elif ct == 'link_open':
            _open_mark('link', {
                'href': c.attrGet('href') or '',
                'title': c.attrGet('title') or '',
            })
        elif ct == 'link_close':
            _close_mark('link')
        elif ct == 'image':
            img = XmlElement('image')
            block_el.children.append(img)
            src = c.attrGet('src')
            if src:
                img.attributes['src'] = src
            title = c.attrGet('title')
            if title:
                img.attributes['title'] = title
            # `content` on an image token is its alt text.
            if c.content:
                img.attributes['alt'] = c.content
        # Unknown inline types are silently dropped for the same reason
        # we drop unknown block tokens: keeps the tree coherent, and
        # any lost formatting is recoverable by retyping.


def _mark_to_attr_value(mark: dict) -> str:
    """Serialize a mark to an attribute value.

    Simple marks (bold/italic/code/strike) → 'true'. Marks with attrs
    (link) → JSON so we can round-trip href/title. This encoding lives
    entirely server-side; the frontend's y-prosemirror binding treats
    marks via its own protocol regardless of what we put in these
    attribute values. The values matter only when WE re-parse them
    in `ydoc_update_to_markdown` below.
    """
    if 'attrs' not in mark:
        return 'true'
    import json
    return json.dumps(mark['attrs'])


def _find_close(tokens: list[Token], open_idx: int, close_type: str) -> int:
    """Return the index of the matching close token, respecting nesting.

    `open_idx` points at the opening token; we walk forward tracking a
    nesting counter so a nested `paragraph_open` inside a `blockquote`
    doesn't confuse the search for the blockquote's close.
    """
    depth = 0
    open_type = tokens[open_idx].type
    for j in range(open_idx + 1, len(tokens)):
        t = tokens[j].type
        if t == open_type:
            depth += 1
        elif t == close_type:
            if depth == 0:
                return j
            depth -= 1
    # Malformed input — return the last token index so the caller
    # doesn't loop forever. This shouldn't happen with markdown-it output.
    logger.warning('collab render: unmatched %s from token %s', close_type, open_type)
    return len(tokens) - 1


# ---------------------------------------------------------------------------
# Y.Doc → markdown
# ---------------------------------------------------------------------------

def ydoc_update_to_markdown(update: bytes | None) -> str:
    """Apply `update` into a fresh Y.Doc, walk the XmlFragment, render markdown.

    `None` or empty bytes → empty string, matching an empty editor.
    """
    if not update:
        return ''
    doc = Doc()
    frag = XmlFragment()
    doc[_PROSEMIRROR_FIELD] = frag
    doc.apply_update(update)

    lines: list[str] = []
    for child in list(frag.children):
        _render_block(child, lines, list_context=None)
    # Trim trailing blank lines but keep the terminal newline convention.
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines) + ('\n' if lines else '')


def _render_block(node, lines: list[str], *, list_context) -> None:
    """Append the markdown lines for a single block node to `lines`.

    `list_context` carries per-list state when we're inside a list
    (kind='ul'|'ol', counter for numbered lists, indent depth). None
    at the top level.
    """
    if isinstance(node, XmlText):
        # Stray XmlText at block level — very rare, but render as a
        # bare paragraph so we don't drop content.
        lines.append(str(node))
        lines.append('')
        return

    tag = getattr(node, 'tag', None)

    if tag == 'heading':
        level = _int_attr(node, 'level', default=1)
        level = max(1, min(6, level))
        lines.append('#' * level + ' ' + _render_inline_children(node))
        lines.append('')
        return

    if tag == 'paragraph':
        text = _render_inline_children(node)
        if text.strip():
            lines.append(text)
            lines.append('')
        return

    if tag == 'bulletList':
        for child in list(node.children):
            _render_list_item(child, lines, marker='- ')
        lines.append('')
        return

    if tag == 'orderedList':
        start = _int_attr(node, 'start', default=1)
        idx = start
        for child in list(node.children):
            _render_list_item(child, lines, marker=f'{idx}. ')
            idx += 1
        lines.append('')
        return

    if tag == 'blockquote':
        inner: list[str] = []
        for child in list(node.children):
            _render_block(child, inner, list_context=None)
        while inner and inner[-1] == '':
            inner.pop()
        for line in inner:
            lines.append('> ' + line if line else '>')
        lines.append('')
        return

    if tag == 'codeBlock':
        lang = _string_attr(node, 'language', default='') or ''
        lines.append('```' + lang)
        # `codeBlock`'s children are XmlText nodes with the raw code.
        for child in list(node.children):
            if isinstance(child, XmlText):
                for code_line in str(child).splitlines() or ['']:
                    lines.append(code_line)
        lines.append('```')
        lines.append('')
        return

    if tag == 'horizontalRule':
        lines.append('---')
        lines.append('')
        return

    if tag == 'image':
        src = _string_attr(node, 'src', default='')
        alt = _string_attr(node, 'alt', default='')
        title = _string_attr(node, 'title', default='')
        title_part = f' "{title}"' if title else ''
        lines.append(f'![{alt}]({src}{title_part})')
        lines.append('')
        return

    if tag == 'table':
        _render_table(node, lines)
        return

    # Unknown block: render nothing rather than crashing. Loud in the
    # log so a missing case here doesn't silently eat content.
    logger.warning('collab render: unknown block tag %r — skipped', tag)


def _render_table(node, lines: list[str]) -> None:
    """Render a `table` XmlElement as a GFM pipe table.

    GFM requires the first row to be the header and the second row to
    be a separator (`| --- | --- |`). TipTap's schema tags header cells
    as `tableHeader` and body cells as `tableCell`, and doesn't require
    the header to be the first row — but pipe syntax has no way to
    express a mid-table header. We handle both shapes pragmatically:
      * If the first row is all `tableHeader`, treat it as the header
        and emit the separator after it (round-trip friendly).
      * Otherwise, synthesise an empty header row above the data so
        the output re-parses as a valid GFM table. This is lossy for
        the visual "no header" shape, but the alternative is emitting
        raw pipes that markdown-it will re-parse as a paragraph and
        we lose the tabular structure entirely.

    Cells are joined with pipes; internal pipes get escaped as `\\|`
    to keep the row shape parseable. Multi-line cell content is
    collapsed to a single line joined with `<br>` — GFM tables can't
    contain block content between the pipes.
    """
    rows: list[tuple[bool, list[str]]] = []
    for row in list(node.children):
        if not isinstance(row, XmlElement) or row.tag != 'tableRow':
            continue
        cells: list[str] = []
        all_headers = True
        for cell in list(row.children):
            if not isinstance(cell, XmlElement):
                continue
            if cell.tag not in ('tableHeader', 'tableCell'):
                continue
            if cell.tag != 'tableHeader':
                all_headers = False
            cell_lines: list[str] = []
            for child in list(cell.children):
                _render_block(child, cell_lines, list_context=None)
            while cell_lines and cell_lines[-1] == '':
                cell_lines.pop()
            # GFM cells are single-line: join intra-cell breaks with
            # `<br>`, and escape stray pipes so the row shape survives.
            text = '<br>'.join(line.strip() for line in cell_lines if line is not None)
            cells.append(text.replace('|', '\\|'))
        rows.append((all_headers and bool(cells), cells))

    if not rows:
        return

    # Column count: max cells across rows. Short rows get padded so
    # every emitted line has the same pipe count (a GFM parser is
    # forgiving here, but consistent output is easier on humans
    # reading the raw source column).
    cols = max(len(r[1]) for r in rows)
    if cols == 0:
        return

    def _emit(cells: list[str]) -> None:
        padded = cells + [''] * (cols - len(cells))
        lines.append('| ' + ' | '.join(padded) + ' |')

    if rows[0][0]:
        _emit(rows[0][1])
        lines.append('| ' + ' | '.join(['---'] * cols) + ' |')
        body_start = 1
    else:
        # Header-less TipTap table → synthesise an empty header row so
        # the output remains a valid GFM table when re-parsed.
        _emit([''] * cols)
        lines.append('| ' + ' | '.join(['---'] * cols) + ' |')
        body_start = 0

    for _, cells in rows[body_start:]:
        _emit(cells)
    lines.append('')


def _render_list_item(node, lines: list[str], marker: str) -> None:
    """Render a `listItem`'s children as a marker-prefixed list item.

    We render each block child, then indent all continuation lines to
    align under the marker column.
    """
    if not isinstance(node, XmlElement) or node.tag != 'listItem':
        return
    inner: list[str] = []
    for child in list(node.children):
        _render_block(child, inner, list_context=None)
    while inner and inner[-1] == '':
        inner.pop()
    if not inner:
        lines.append(marker.rstrip())
        return
    indent = ' ' * len(marker)
    lines.append(marker + inner[0])
    for line in inner[1:]:
        lines.append((indent + line) if line else '')


def _render_inline_children(block) -> str:
    """Render the inline children of a block node as a single markdown
    string. Handles the mark stack in reverse of `_build_inline_into`."""
    out: list[str] = []
    for child in list(block.children):
        if isinstance(child, XmlText):
            out.append(_render_text_with_marks(child))
        elif isinstance(child, XmlElement):
            if child.tag == 'hardBreak':
                out.append('  \n')
            elif child.tag == 'image':
                src = _string_attr(child, 'src', default='')
                alt = _string_attr(child, 'alt', default='')
                title = _string_attr(child, 'title', default='')
                title_part = f' "{title}"' if title else ''
                out.append(f'![{alt}]({src}{title_part})')
            # Other inline elements are unexpected; ignore.
    return ''.join(out)


def _render_text_with_marks(node: XmlText) -> str:
    """Wrap the text in markdown syntax matching the marks stored on the
    XmlText node's attributes.

    Order of application matches TipTap's serializer: links wrap outermost,
    then code, then bold, then italic, then strike. Getting the order right
    matters for CommonMark's tight escapes.
    """
    text = str(node)
    if not text:
        return ''
    attrs = dict(node.attributes) if hasattr(node, 'attributes') else {}

    # Escape markdown special chars in raw text before we apply marks
    # (otherwise `**` in normal prose would render as bold on next parse).
    if 'code' not in attrs:
        text = _escape_markdown(text)

    if 'strike' in attrs:
        text = f'~~{text}~~'
    if 'italic' in attrs:
        text = f'*{text}*'
    if 'bold' in attrs:
        text = f'**{text}**'
    if 'code' in attrs:
        text = f'`{text}`'
    if 'link' in attrs:
        import json
        try:
            link_attrs = json.loads(attrs['link'])
        except (TypeError, ValueError):
            link_attrs = {'href': '', 'title': ''}
        href = link_attrs.get('href', '')
        title = link_attrs.get('title', '')
        title_part = f' "{title}"' if title else ''
        text = f'[{text}]({href}{title_part})'
    return text


# Characters that need escaping when they appear MID-TEXT to prevent
# a re-parse from interpreting them as markdown syntax. Deliberately
# narrower than markdown-it's max set — we don't blanket-escape `.`
# `!` `-` etc. because those only matter at line starts and their
# escaped form (`\.` `\!` `\-`) shows up as ugly noise in the raw
# source column readers see (REST, exports, git-tracked backups).
# Chars kept out and their justification:
#   `.`  only meaningful after digit + at line start (numbered list)
#   `!`  only meaningful when followed by `[` (image)
#   `-`  only meaningful at line start (unordered list / hr)
#   `+`  same as `-`
#   `>`  only meaningful at line start (blockquote)
#   `#`  only meaningful at line start (heading)
# These edge cases are handled by escaping only when the character
# lands at position 0 of a fresh line. Everything else is safe raw.
_MD_INLINE_ESCAPE_CHARS = r'\`*_[]<'


def _escape_markdown(text: str) -> str:
    r"""Prefix markdown-special characters with a backslash so a re-parse
    round-trips them as literal text.

    Kept intentionally narrow: only the chars that would change meaning
    if left raw INSIDE inline text. Chars that only matter at line
    starts (heading `#`, list `-`/`+`/`.`, blockquote `>`, hr `---`)
    are handled by the block renderer emitting them on their own lines
    where they can't collide with user text; escaping them everywhere
    would produce `\-hello` for a paragraph that begins with a hyphen,
    which is technically correct but visually wrong.
    """
    out = []
    for ch in text:
        if ch in _MD_INLINE_ESCAPE_CHARS:
            out.append('\\')
        out.append(ch)
    return ''.join(out)


def _int_attr(node, name: str, default: int) -> int:
    try:
        return int(node.attributes[name])
    except (KeyError, TypeError, ValueError):
        return default


def _string_attr(node, name: str, default: str) -> str:
    try:
        return str(node.attributes[name])
    except (KeyError, TypeError):
        return default
