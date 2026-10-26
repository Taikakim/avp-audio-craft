# Owner: WINTERMUTE (created 2026-10-26)
"""Marker tests. Cover Review Focus 1 (word/URL/attribute/entity safety, valid HTML) and 2 (longest match)."""
from html.parser import HTMLParser

from glossary.mark import mark, used_ids

GL = [
    {"id": "lora", "term": "LoRA"},
    {"id": "lora-a", "term": "LoRA A"},
    {"id": "weight", "term": "weight"},
    {"id": "weight-decay", "term": "weight decay"},
    {"id": "weight-matrix", "term": "weight matrix", "aliases": ["weight matrices"]},
    {"id": "matrix", "term": "matrix", "aliases": ["matrices"]},
    {"id": "bias", "term": "bias"},
    {"id": "policy", "term": "policy"},
    {"id": "amp", "term": "amp"},
]
HREF = "../help/glossary.html"


def rep(eid, text):
    return f'<span class="gl gl-rep" data-term="{eid}">{text}</span>'


def a(eid, text, href=HREF):
    return f'<a class="gl" data-term="{eid}" href="{href}#{eid}">{text}</a>'


class _Nest(HTMLParser):
    """Records the deepest <a> nesting seen."""
    def __init__(self):
        super().__init__()
        self.depth = self.max = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.depth += 1
            self.max = max(self.max, self.depth)

    def handle_endtag(self, tag):
        if tag == "a":
            self.depth -= 1


def max_anchor_depth(html):
    p = _Nest()
    p.feed(html)
    return p.max


def test_every_occurrence_is_marked_and_case_is_preserved():
    out = mark("<p>Weight, then WEIGHT and weight again.</p>", GL, first_per_section=False)
    assert out == f"<p>{a('weight', 'Weight')}, then {a('weight', 'WEIGHT')} and {a('weight', 'weight')} again.</p>"


def test_simple_plurals_and_aliases():
    out = mark("<p>weights, policies, matrices, biases</p>", GL)
    assert out == f"<p>{a('weight', 'weights')}, {a('policy', 'policies')}, {a('matrix', 'matrices')}, {a('bias', 'biases')}</p>"


def test_longest_match_wins():
    out = mark("<p>LoRA A and LoRA, weight decay, weight matrix, weight.</p>", GL)
    assert out == ("<p>" + a("lora-a", "LoRA A") + " and " + a("lora", "LoRA") + ", " + a("weight-decay", "weight decay")
                   + ", " + a("weight-matrix", "weight matrix") + ", " + a("weight", "weight") + ".</p>")


def test_longest_match_beats_a_shorter_term_that_starts_earlier_in_the_same_word_group():
    out = mark("<p>Several weight matrices share LoRA Adapters.</p>", GL)
    assert a("weight-matrix", "weight matrices") in out          # alias, longer than "weight"
    assert a("lora", "LoRA") in out and "LoRA A</a>" not in out   # "LoRA A" must not eat the A of "Adapters"


def test_multiword_term_matches_across_a_line_break():
    out = mark("<p>the weight\n   matrix here</p>", GL)
    assert a("weight-matrix", "weight\n   matrix") in out


def test_terms_inside_words_are_not_marked():
    html = "<p>reweighted weightless ampere biased policyholder LoRAs-like sweight-sharing</p>"
    out = mark(html, GL)
    for eid in ("weight", "amp", "bias", "policy"):
        assert f'data-term="{eid}"' not in out
    assert 'data-term="lora"' not in out or out.count('data-term="lora"') == 1   # "LoRAs" is a plural of LoRA


def test_urls_in_text_are_not_marked():
    out = mark("<p>see https://example.com/weight/bias.html and www.weight.org, then weight</p>", GL)
    assert "https://example.com/weight/bias.html and www.weight.org" in out
    assert out.count('data-term="weight"') == 1


def test_attributes_are_never_touched():
    html = '<p><img src="weight.png" alt="the weight matrix" title="bias"><span title="weight" data-x="bias">weight</span></p>'
    out = mark(html, GL)
    assert out == ('<p><img src="weight.png" alt="the weight matrix" title="bias">'
                   f'<span title="weight" data-x="bias">{a("weight", "weight")}</span></p>')


def test_entities_survive_and_are_not_marked():
    assert mark("<p>Tom &amp; Jerry &lt;3 &#38; &nbsp;</p>", GL) == "<p>Tom &amp; Jerry &lt;3 &#38; &nbsp;</p>"
    out = mark("<p>weight &amp; bias</p>", GL)
    assert out == f"<p>{a('weight', 'weight')} &amp; {a('bias', 'bias')}</p>"


def test_skip_zones():
    html = ("<h1>weight</h1><h2>weight</h2><h6>weight</h6><code>weight</code><pre>weight</pre>"
            '<a href="x">weight</a><figure><figcaption>weight</figcaption></figure>'
            "<table><tr><th>weight</th><td>bias</td></tr></table><script>var weight=1;</script><style>.weight{}</style>")
    out = mark(html, GL)
    assert out.count('data-term="weight"') == 0
    assert a("bias", "bias") in out                                     # td is not a skip zone
    assert "<script>var weight=1;</script>" in out and "<style>.weight{}</style>" in out


def test_marked_markup_has_no_nested_anchors_and_is_stable():
    html = '<p><a href="https://x.org">a weight link</a> and weight and <strong>weight decay</strong></p>'
    out = mark(html, GL)
    assert max_anchor_depth(out) == 1
    assert out.count('data-term="weight"') == 1 and out.count('data-term="weight-decay"') == 1
    assert mark(out, GL) == out                                         # marking marked HTML changes nothing


def test_inline_markup_around_terms_is_kept():
    out = mark("<p>a <em>weight</em> and <strong>LoRA A</strong></p>", GL)
    assert out == f"<p>a <em>{a('weight', 'weight')}</em> and <strong>{a('lora-a', 'LoRA A')}</strong></p>"


def test_markup_without_terms_comes_back_byte_identical():
    html = ("<p class='x' data-a=\"1\">Hello<br/>there<img src=a.png></p><!-- a comment -->"
            "<ul>\n<li>one</li>\n</ul><table class=\"listing\"><tr><td>x</td></tr></table>")
    assert mark(html, GL) == html


def test_own_term_is_consumed_but_not_linked():
    gl = [e for e in GL]
    out = mark("<p>The weight matrix holds one weight per link.</p>", gl, glossary_href="glossary.html",
               exclude_id="weight-matrix")
    # "weight matrix" is the entry's own term: no link, and its inner "weight" is NOT linked either
    assert out == f"<p>The weight matrix holds one {a('weight', 'weight', 'glossary.html')} per link.</p>"


def test_custom_href_is_used():
    out = mark("<p>bias</p>", GL, glossary_href="glossary.html")
    assert out == f'<p>{a("bias", "bias", "glossary.html")}</p>'


def test_empty_glossary_changes_nothing():
    assert mark("<p>weight</p>", []) == "<p>weight</p>"


def test_used_ids_lists_marked_terms_only():
    out = mark("<p>weight and bias and <a href='x'>amp</a></p>", GL)
    assert used_ids(out) == {"weight", "bias"}
    assert used_ids('<a class="other" data-term="weight" href="x">w</a>') == set()


def test_unterminated_and_terminated_references_come_back_byte_identical():
    for html in ("<p>AT&T weight</p>", "<p>R&D &copy 2020</p>", "<p>a&#38 b</p>", "<p>x &amp; y &#169; z</p>",
                 "<p>line one\nAT&T &#x26 two\n&amp;</p>"):
        out = mark(html, [{"id": "nomatch", "term": "zzz"}])
        assert out == html
    assert mark("<p>AT&T weight</p>", GL) == f"<p>AT&T {a('weight', 'weight')}</p>"
    assert mark("<p>R&D &copy 2020 bias</p>", GL) == f"<p>R&D &copy 2020 {a('bias', 'bias')}</p>"


# ---- first occurrence per section --------------------------------------------------------------------

def test_second_occurrence_in_a_section_is_a_rep_span():
    out = mark("<p>Weight, then WEIGHT.</p><p>And weight.</p>", GL)
    assert out == f"<p>{a('weight', 'Weight')}, then {rep('weight', 'WEIGHT')}.</p><p>And {rep('weight', 'weight')}.</p>"
    assert "href" not in rep("weight", "x") and "tabindex" not in out and "role=" not in out


def test_heading_starts_a_new_section():
    out = mark("<p>weight</p><h2>Title</h2><p>weight, weight</p><h3>Sub</h3><p>weight</p>", GL)
    assert out == (f"<p>{a('weight', 'weight')}</p><h2>Title</h2><p>{a('weight', 'weight')}, {rep('weight', 'weight')}</p>"
                   f"<h3>Sub</h3><p>{a('weight', 'weight')}</p>")


def test_each_call_is_its_own_section():
    assert mark("<p>bias</p>", GL) == mark("<p>bias</p>", GL) == f"<p>{a('bias', 'bias')}</p>"


def test_alias_and_plural_count_as_the_main_term():
    out = mark("<p>weight matrix, then weight matrices and matrices, matrix</p>", GL)
    assert out == (f"<p>{a('weight-matrix', 'weight matrix')}, then {rep('weight-matrix', 'weight matrices')} and "
                   f"{a('matrix', 'matrices')}, {rep('matrix', 'matrix')}</p>")
    out = mark("<p>bias, biases</p>", GL)
    assert out == f"<p>{a('bias', 'bias')}, {rep('bias', 'biases')}</p>"


def test_skip_zones_still_skipped_and_do_not_use_up_the_link():
    out = mark("<code>weight</code><a href='x'>weight</a><h2>weight</h2><p>weight</p>", GL)
    assert out.count('data-term="weight"') == 1 and a("weight", "weight") in out and "gl-rep" not in out


def test_used_ids_counts_spans():
    out = mark("<p>weight</p><p>weight and bias</p>", GL)
    assert used_ids(out) == {"weight", "bias"}
    assert used_ids(rep("amp", "amp")) == {"amp"}
    assert used_ids('<span class="other" data-term="weight">w</span>') == set()


def test_first_per_section_false_links_everywhere():
    out = mark("<p>weight weight</p><h2>t</h2><p>weight</p>", GL, first_per_section=False)
    assert out.count('<a class="gl"') == 3 and "gl-rep" not in out


def test_marking_marked_html_is_stable_with_spans():
    out = mark("<p>weight and weight and bias</p>", GL)
    assert mark(out, GL) == out
