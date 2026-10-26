# Owner: WINTERMUTE (created 2026-10-26)
"""Mark glossary terms in rendered HTML: every occurrence becomes <a class="gl" data-term=ID href=...>.

Works on text nodes only (html.parser), so attributes, entities, URLs and skip zones are never touched.
"""
import re
from functools import lru_cache
from html import escape
from html.parser import HTMLParser

SKIP_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "a", "figcaption", "th", "script", "style"})
_URL = r"(?:https?://|www\.)[^\s<>\"']+"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()


def _plurals(form: str) -> list:
    low = form.lower()
    if len(low) > 1 and low.endswith("y") and low[-2] not in "aeiou":
        return [form[:-1] + "ies"]
    if low.endswith(("s", "x", "z", "ch", "sh")):
        return [form + "es"]
    return [form + "s"]


@lru_cache(maxsize=16)
def _matcher(key):
    """key = ((id, term, (aliases...)), ...) -> (compiled regex or None, {normalised variant: id})."""
    variants = {}
    for eid, term, aliases in key:                      # explicit forms win over generated plurals
        for f in (term,) + aliases:
            variants.setdefault(_norm(f), eid)
    for eid, term, aliases in key:
        for f in (term,) + aliases:
            for p in _plurals(f):
                variants.setdefault(_norm(p), eid)
    if not variants:
        return None, variants
    body = "|".join(re.escape(v).replace(r"\ ", r"\s+") for v in sorted(variants, key=len, reverse=True))
    rx = re.compile(rf"(?P<url>{_URL})|(?<![\w/@.#-])(?P<t>{body})(?![\w@]|[/.-]\w)", re.I)
    return rx, variants


class _Marker(HTMLParser):
    def __init__(self, rx, variants, href, exclude_id):
        super().__init__(convert_charrefs=False)
        self.rx, self.variants, self.href, self.exclude_id = rx, variants, href, exclude_id
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in SKIP_TAGS:
            self.skip += 1

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")

    def handle_pi(self, data):
        self.out.append(f"<?{data}>")

    def unknown_decl(self, data):
        self.out.append(f"<![{data}]>")

    def handle_data(self, data):
        self.out.append(data if self.skip else self.rx.sub(self._sub, data))

    def _sub(self, m):
        if m.group("url"):
            return m.group(0)
        text = m.group("t")
        eid = self.variants.get(_norm(text))
        if eid is None or eid == self.exclude_id:
            return text                                  # own term: consumed (longest match) but not linked
        e = escape(eid, quote=True)
        return f'<a class="gl" data-term="{e}" href="{escape(self.href, quote=True)}#{e}">{text}</a>'


def mark(html: str, glossary, glossary_href: str = "../help/glossary.html", exclude_id=None) -> str:
    """Return `html` with every glossary term occurrence wrapped as <a class="gl" ...> (contract C2).

    glossary: list of entry dicts (needs id, term, optional aliases). exclude_id: the entry whose own
    term must not be linked (used when marking that entry's own text).
    """
    key = tuple((e["id"], e["term"], tuple(e.get("aliases") or ())) for e in glossary)
    rx, variants = _matcher(key)
    if rx is None:
        return html
    p = _Marker(rx, variants, glossary_href, exclude_id)
    p.feed(html)
    p.close()
    return "".join(p.out)


class _Used(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            if "gl" in (d.get("class") or "").split() and d.get("data-term"):
                self.ids.add(d["data-term"])


def used_ids(html: str) -> set:
    """The entry ids that `html` links as marked terms."""
    p = _Used()
    p.feed(html)
    p.close()
    return p.ids
