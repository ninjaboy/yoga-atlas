#!/usr/bin/env python3
"""Build a static GitHub-Pages site (docs/) from the Yoga Atlas vault.

Converts the Obsidian markdown notes to linked HTML: resolves [[wiki-links]],
renders ```mermaid``` diagrams via mermaid.js, builds a grouped sidebar, and writes a
self-contained themed site into ../docs (Pages serves it from /docs on master).

    python3 build_site.py        # regenerate docs/
"""
from __future__ import annotations
import html, re, shutil
from pathlib import Path
import markdown

SITE = Path(__file__).resolve().parent
VAULT = SITE.parent
DOCS = VAULT / "docs"

# Vault folders to publish, in nav order → (folder, section label)
SECTIONS = [
    ("00-Maps", "Overview"),
    ("10-Traditions", "History & Traditions"),
    ("20-Schools", "Modern Schools"),
    ("30-Asanas", "Asanas"),
    ("40-Texts", "Texts"),
    ("50-Figures", "Figures"),
    ("60-Concepts", "Philosophy"),
    ("70-Practices", "Practices"),
    ("80-Media", "Media"),
]

WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def collect_pages():
    """Return [(stem, title, folder, src_path)] for every note, + a stem→href map."""
    pages, stem_href = [], {}
    for folder, _ in SECTIONS:
        for md in sorted((VAULT / folder).glob("*.md")):
            stem = md.stem
            href = f"{stem}.html"
            title = stem.replace("-", " ")
            m = re.search(r'^title:\s*"?(.+?)"?\s*$', md.read_text(), re.M)
            if m:
                title = m.group(1)
            pages.append((stem, title, folder, md))
            stem_href[stem] = href
    return pages, stem_href


def render_body(text, stem_href):
    text = FRONTMATTER.sub("", text, count=1)

    # 1) pull mermaid blocks out before markdown mangles them
    blocks = []
    def _stash(m):
        blocks.append(m.group(1))
        return f"\n\nMERMAIDBLOCK{len(blocks)-1}\n\n"
    text = MERMAID.sub(_stash, text)

    # 2) resolve [[wiki-links]] → <a> when the target exists, else plain text
    def _link(m):
        target, alias = m.group(1).strip(), (m.group(2) or "").strip()
        key = target.split("/")[-1].replace(".md", "")
        label = alias or key.replace("-", " ")
        if key in stem_href:
            return f"[{label}]({stem_href[key]})"
        return label
    text = WIKILINK.sub(_link, text)

    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list",
                                       "sane_lists", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(text)

    # 3) reinsert mermaid as raw <pre class="mermaid">
    for i, raw in enumerate(blocks):
        holder = f"<p>MERMAIDBLOCK{i}</p>"
        body = body.replace(holder, f'<pre class="mermaid">{html.escape(raw)}</pre>')

    # 4) any paragraph that STARTS with an embedded image → a <figure>, with the
    #    rest of the paragraph as the <figcaption> (our images are always
    #    paragraph-leading, optionally followed by an italic source/licence line).
    def _fig(m):
        img = m.group(1)
        cap = m.group(2).strip()
        # drop the markdown emphasis wrapper around the caption if present
        cap = re.sub(r'^<em>(.*)</em>$', r'\1', cap, flags=re.DOTALL).strip()
        caphtml = f'<figcaption>{cap}</figcaption>' if cap else ''
        return f'<figure>{img}{caphtml}</figure>'
    # two-paragraph form first (img alone, caption in next <p>)
    body = re.sub(r'<p>(<img[^>]+?/?>)</p>\s*<p>(.*?)</p>', _fig, body, flags=re.DOTALL)
    # same-paragraph form (img then caption text in the same <p>)
    body = re.sub(r'<p>(<img[^>]+?/?>)\s*(.*?)</p>', _fig, body, flags=re.DOTALL)

    return body, getattr(md, "toc", "")


TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Yoga Atlas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&family=Spectral:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">
<style>
 :root{{
   --bg:#15131a;--panel:#1b1922;--ink:#ece8f1;--soft:#cfc9da;--muted:#9b95ab;
   --accent:#d8b86a;--accent2:#b98a5e;--line:#2b2834;--quote:#1f1b16;
   --serif:'Spectral',Georgia,serif; --display:'Cormorant Garamond',Georgia,serif;
   --sans:'Inter',-apple-system,Segoe UI,Roboto,sans-serif;
 }}
 *{{box-sizing:border-box}}
 html{{scroll-behavior:smooth}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.72 var(--serif)}}
 .wrap{{display:flex;min-height:100vh}}
 /* --- sidebar --- */
 nav{{width:280px;flex:0 0 280px;background:var(--panel);border-right:1px solid var(--line);
   padding:26px 20px;position:sticky;top:0;height:100vh;overflow:auto;font-family:var(--sans)}}
 nav .brand{{font-family:var(--display);font-size:27px;font-weight:700;margin:0 0 2px;color:var(--ink)}}
 nav .brand a{{color:inherit;text-decoration:none}}
 nav .sub{{color:var(--muted);font-size:12px;letter-spacing:.04em;margin-bottom:22px}}
 nav .grp{{color:var(--accent);font-size:10.5px;font-weight:600;letter-spacing:.12em;
   text-transform:uppercase;margin:18px 0 5px}}
 nav a.lnk{{display:block;color:var(--soft);text-decoration:none;padding:5px 10px;border-radius:7px;font-size:14px}}
 nav a.lnk:hover{{background:#262330;color:var(--ink)}}
 nav a.active{{background:linear-gradient(90deg,#2f2818,#241f17);color:var(--accent);font-weight:500}}
 /* --- content --- */
 main{{flex:1;max-width:1080px;margin:0 auto;padding:0 46px 110px;display:flex;gap:40px}}
 .article{{flex:1;min-width:0;max-width:760px;margin:0 auto;padding-top:40px}}
 h1,h2,h3,h4{{font-family:var(--display);font-weight:600;line-height:1.2;color:var(--ink)}}
 .article h1{{font-size:2.7rem;margin:.2em 0 .5em;font-weight:700;letter-spacing:.01em}}
 .article h2{{font-size:1.75rem;margin:1.9em 0 .5em;padding-top:.4em;border-top:1px solid var(--line)}}
 .article h3{{font-size:1.32rem;margin:1.4em 0 .4em;color:var(--soft)}}
 .article h4{{font-size:1.08rem;color:var(--accent2);margin:1.2em 0 .3em}}
 p{{margin:.8em 0}}
 a{{color:var(--accent);text-decoration-color:rgba(216,184,106,.4);text-underline-offset:2px}}
 a:hover{{text-decoration-color:var(--accent)}}
 code{{background:#262330;padding:.12em .4em;border-radius:4px;font-size:.88em;font-family:var(--sans)}}
 strong{{color:#fff;font-weight:600}}
 em{{color:var(--soft)}}
 ul,ol{{padding-left:1.3em}} li{{margin:.25em 0}}
 hr{{border:none;border-top:1px solid var(--line);margin:2.2em 0}}
 /* --- figures --- */
 figure{{margin:1.6em 0;text-align:center}}
 figure img{{max-width:100%;height:auto;max-height:560px;width:auto;border-radius:10px;
   background:#faf8f3;box-shadow:0 6px 26px rgba(0,0,0,.4);border:1px solid #00000040}}
 figcaption{{font-family:var(--sans);font-size:12.5px;color:var(--muted);line-height:1.5;
   margin-top:.6em;max-width:620px;margin-left:auto;margin-right:auto}}
 figcaption a{{color:var(--accent2)}}
 /* --- quotes (canonical citations) --- */
 blockquote{{border:none;margin:1.4em 0;padding:1em 1.3em;background:var(--quote);
   border-left:3px solid var(--accent);border-radius:0 8px 8px 0;color:#e7ddca;
   font-style:italic;font-size:1.06em}}
 blockquote p{{margin:.3em 0}}
 blockquote em{{color:#cbb98f}}
 /* --- tables --- */
 table{{border-collapse:collapse;width:100%;margin:1.3em 0;font-size:.93em;font-family:var(--sans)}}
 th,td{{border:1px solid var(--line);padding:8px 11px;text-align:left;vertical-align:top}}
 th{{background:#221f2b;color:var(--accent);font-weight:600}}
 tr:nth-child(even) td{{background:#1a1822}}
 /* --- code / mermaid --- */
 pre{{background:#100f17;border:1px solid var(--line);padding:14px;border-radius:8px;overflow:auto}}
 pre.mermaid{{background:#f6f3ec;color:#222;text-align:center;border:none}}
 /* --- on-this-page TOC --- */
 .toc{{flex:0 0 200px;font-family:var(--sans);font-size:13px;position:sticky;top:0;
   align-self:flex-start;padding-top:54px;max-height:100vh;overflow:auto}}
 .toc .ttl{{color:var(--accent);font-size:10.5px;font-weight:600;letter-spacing:.12em;
   text-transform:uppercase;margin-bottom:8px}}
 .toc ul{{list-style:none;padding:0;margin:0;border-left:1px solid var(--line)}}
 .toc li{{margin:0}}
 .toc a{{display:block;color:var(--muted);text-decoration:none;padding:3px 0 3px 12px;
   margin-left:-1px;border-left:2px solid transparent;line-height:1.35}}
 .toc a:hover{{color:var(--ink);border-left-color:var(--accent2)}}
 /* --- hero (home) --- */
 .hero{{margin:18px 0 30px;padding:38px 34px;border-radius:14px;
   background:radial-gradient(120% 140% at 0% 0%,#26201a 0%,#1a1822 55%);
   border:1px solid var(--line)}}
 .hero h1{{font-size:3.2rem;margin:.1em 0;border:none}}
 .hero .tag{{font-family:var(--sans);color:var(--soft);font-size:15px;max-width:560px}}
 .hero .chips{{margin-top:14px}}
 .hero .chip{{display:inline-block;font-family:var(--sans);font-size:11.5px;color:var(--accent);
   border:1px solid var(--accent2);border-radius:20px;padding:3px 11px;margin:3px 6px 0 0}}
 .foot{{color:var(--muted);font-size:12px;font-family:var(--sans);margin-top:60px;
   border-top:1px solid var(--line);padding-top:16px}}
 @media(max-width:960px){{
   nav{{display:none}} main{{padding:0 20px 70px;flex-direction:column}}
   .toc{{display:none}} .article{{padding-top:24px}}
   .article h1{{font-size:2.1rem}} .hero h1{{font-size:2.3rem}}
 }}
</style></head><body><div class="wrap">
<nav>
<div class="brand"><a href="Overview.html">🧘 Yoga Atlas</a></div>
<div class="sub">a sourced, open-licence vault</div>
{nav}
<div class="grp">Project</div>
<a class="lnk" href="https://github.com/ninjaboy/yoga-atlas">GitHub repository ↗</a>
</nav>
<main>
<article class="article">{hero}{body}
<div class="foot">Yoga Atlas — a sourced, open-licence knowledge vault. Every image is
Public-Domain / Creative-Commons with attribution; contested and modern claims are
flagged in-text. Generated from the Obsidian source.</div>
</article>
{toc}
</main></div>
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
mermaid.initialize({{startOnLoad:true, theme:"neutral"}});
</script></body></html>"""


def build():
    pages, stem_href = collect_pages()
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    (DOCS / ".nojekyll").write_text("")           # serve our HTML as-is

    home_stem = "Overview"
    HERO = (
        '<div class="hero"><h1>🧘 Yoga Atlas</h1>'
        '<div class="tag">A sourced, open-licence knowledge vault on yoga — its history, '
        'traditions, texts, figures, asanas, practices and philosophy — illustrated only with '
        'Public-Domain &amp; Creative-Commons media and grounded in the canonical texts.</div>'
        '<div class="chips"><span class="chip">10 articles</span>'
        '<span class="chip">canonical quotes</span><span class="chip">open-licence images</span>'
        '<span class="chip">cited throughout</span></div></div>'
    )
    for stem, title, folder, md in pages:
        # nav with the current page marked active
        nav = []
        for fold, label in SECTIONS:
            items = [p for p in pages if p[2] == fold]
            if not items:
                continue
            nav.append(f'<div class="grp">{html.escape(label)}</div>')
            for s2, t2, _, _ in items:
                cls = "lnk active" if s2 == stem else "lnk"
                nav.append(f'<a class="{cls}" href="{s2}.html">{html.escape(t2)}</a>')
        body, toc_html = render_body(md.read_text(), stem_href)
        # on-this-page TOC (skip if too few headings)
        toc = ""
        if toc_html and toc_html.count("<li") >= 3:
            toc = f'<aside class="toc"><div class="ttl">On this page</div>{toc_html}</aside>'
        hero = HERO if stem == home_stem else ""
        page = TEMPLATE.format(title=html.escape(title), nav="\n".join(nav),
                               body=body, toc=toc, hero=hero)
        (DOCS / f"{stem}.html").write_text(page)
        if stem == home_stem:
            (DOCS / "index.html").write_text(page)

    print(f"Built {len(pages)} pages → {DOCS}")


if __name__ == "__main__":
    build()
