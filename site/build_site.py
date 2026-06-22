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

    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"])

    # 3) reinsert mermaid as raw <pre class="mermaid">
    for i, raw in enumerate(blocks):
        holder = f"<p>MERMAIDBLOCK{i}</p>"
        body = body.replace(holder, f'<pre class="mermaid">{html.escape(raw)}</pre>')
    return body


TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Yoga Atlas</title>
<style>
 :root{{--bg:#14141b;--panel:#1c1c26;--ink:#e8e6f0;--muted:#9a97ad;--accent:#caa75d;--line:#2c2c3a}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
   font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
 .wrap{{display:flex;min-height:100vh}}
 nav{{width:270px;flex:0 0 270px;background:var(--panel);border-right:1px solid var(--line);
   padding:22px 18px;position:sticky;top:0;height:100vh;overflow:auto}}
 nav h1{{font-size:18px;margin:0 0 4px}} nav .sub{{color:var(--muted);font-size:12px;margin-bottom:18px}}
 nav .grp{{color:var(--accent);font-size:11px;letter-spacing:.08em;text-transform:uppercase;margin:16px 0 6px}}
 nav a{{display:block;color:var(--ink);text-decoration:none;padding:4px 8px;border-radius:6px;font-size:14px}}
 nav a:hover{{background:#262633}} nav a.active{{background:#2f2a1f;color:var(--accent)}}
 main{{flex:1;max-width:860px;margin:0 auto;padding:42px 40px 90px}}
 main h1{{border-bottom:1px solid var(--line);padding-bottom:.3em}}
 a{{color:var(--accent)}} code{{background:#262633;padding:.1em .35em;border-radius:4px}}
 pre{{background:#11111a;border:1px solid var(--line);padding:14px;border-radius:8px;overflow:auto}}
 pre.mermaid{{background:#f6f4ee;color:#222;text-align:center}}
 table{{border-collapse:collapse;width:100%;margin:1em 0}}
 th,td{{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}}
 th{{background:#23232f}} blockquote{{border-left:3px solid var(--accent);margin:1em 0;
   padding:.2em 1em;background:#1e1c17;color:#d8d2c2}}
 .foot{{color:var(--muted);font-size:12px;margin-top:48px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body><div class="wrap">
<nav><h1>🧘 Yoga Atlas</h1><div class="sub">sourced · open-licence</div>
{nav}
<div class="grp">Repo</div>
<a href="https://github.com/ninjaboy/yoga-atlas">GitHub ↗</a>
</nav>
<main>{body}
<div class="foot">Yoga Atlas — a sourced, open-licence knowledge vault. Generated from the
Obsidian vault; contested and modern claims are flagged in-text.</div>
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
    for stem, title, folder, md in pages:
        # nav with the current page marked active
        nav = []
        for fold, label in SECTIONS:
            items = [p for p in pages if p[2] == fold]
            if not items:
                continue
            nav.append(f'<div class="grp">{html.escape(label)}</div>')
            for s2, t2, _, _ in items:
                cls = " class=\"active\"" if s2 == stem else ""
                nav.append(f'<a href="{s2}.html"{cls}>{html.escape(t2)}</a>')
        body = render_body(md.read_text(), stem_href)
        page = TEMPLATE.format(title=html.escape(title), nav="\n".join(nav), body=body)
        (DOCS / f"{stem}.html").write_text(page)
        if stem == home_stem:
            (DOCS / "index.html").write_text(page)

    print(f"Built {len(pages)} pages → {DOCS}")


if __name__ == "__main__":
    build()
