#!/usr/bin/env python3
"""
Yoga Atlas — standalone deep-research pipeline.

A self-contained orchestrator (NOT a Claude Code skill/hook). It walks the stages
in plan.yaml and, for each one:

    1. RESEARCH  — calls Claude with the web-search tool to research the stage deeply.
    2. CRITIQUE  — a second Claude call checks the draft against the stage checklist
                   and returns a list of GAPS.
    3. GAP-FILL  — if there are gaps (and retries remain), runs a focused follow-up
                   research pass and merges it in.
    4. WRITE     — saves the result as an Obsidian-style markdown note in the vault.

A persistent ledger (state.json) tracks cumulative spend and completed stages, so a
re-run RESUMES where it left off. BUDGET GUARD: when cumulative spend crosses half
the budget it STOPS and asks you whether to continue; at the full budget it hard-stops.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 research_pipeline.py                 # run with defaults
    python3 research_pipeline.py --budget 50     # $50 cap (asks at $25)
    python3 research_pipeline.py --research-model claude-sonnet-4-6   # cheaper
    python3 research_pipeline.py --only 10-history       # run one stage
    python3 research_pipeline.py --force         # re-run completed stages
    python3 research_pipeline.py --yes           # don't pause at the 50% checkpoint

Requires:  pip install anthropic pyyaml
"""
from __future__ import annotations
import argparse, datetime, json, mimetypes, os, re, sys, textwrap, urllib.request
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")
try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency: pip install anthropic")

ROOT = Path(__file__).resolve().parent          # .../yoga-atlas/research
VAULT = ROOT.parent                             # .../yoga-atlas
PLAN_PATH = ROOT / "plan.yaml"
STATE_PATH = ROOT / "state.json"

# --- Pricing (USD per 1M tokens) + web search. ESTIMATES — edit to match your plan.
# Keep keys as model-id prefixes; the longest matching prefix wins.
PRICING = {
    "claude-opus":   {"in": 15.0, "out": 75.0},
    "claude-sonnet": {"in":  3.0, "out": 15.0},
    "claude-haiku":  {"in":  1.0, "out":  5.0},
}
WEB_SEARCH_USD_PER_CALL = 10.0 / 1000.0          # ~$10 per 1,000 searches

DEFAULT_BUDGET = 50.0                             # USD; ask at half, hard-stop at full
CHECKPOINT_FRAC = 0.5
DEFAULT_RESEARCH_MODEL = "claude-opus-4-8"
DEFAULT_CRITIC_MODEL = "claude-sonnet-4-6"
MAX_GAPFILL_ROUNDS = 2                            # follow-up passes per stage
WEB_SEARCH_MAX_USES = 12                          # searches the model may run per call

# --- Media auto-download (for stages flagged `download: true` in plan.yaml)
ASSETS_DIR = VAULT / "90-Assets"
MEDIA_MAX_BYTES = 40 * 1024 * 1024                # skip anything bigger than 40 MB
HTTP_TIMEOUT = 30
USER_AGENT = "YogaAtlas/1.0 (open-licence research vault; contact: local)"
MEDIA_OK_TYPES = ("image/", "video/", "audio/", "application/pdf")


def price_for(model: str) -> dict:
    best, plen = {"in": 5.0, "out": 25.0}, -1
    for prefix, p in PRICING.items():
        if model.startswith(prefix) and len(prefix) > plen:
            best, plen = p, len(prefix)
    return best


def cost_of(model: str, usage) -> float:
    """USD for one response, from token usage + server web-search count."""
    p = price_for(model)
    tin = getattr(usage, "input_tokens", 0) or 0
    tout = getattr(usage, "output_tokens", 0) or 0
    # cache tokens, if present, are billed ~like input — approximate as input rate.
    tin += getattr(usage, "cache_read_input_tokens", 0) or 0
    tin += getattr(usage, "cache_creation_input_tokens", 0) or 0
    cost = tin / 1e6 * p["in"] + tout / 1e6 * p["out"]
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        cost += (getattr(stu, "web_search_requests", 0) or 0) * WEB_SEARCH_USD_PER_CALL
    return cost


# ---------------------------------------------------------------- state / ledger
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"spent": 0.0, "stages": {}, "checkpoint_ack": False, "log": []}


def save_state(s: dict) -> None:
    STATE_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False))


def record(state: dict, model: str, usage, label: str) -> None:
    c = cost_of(model, usage)
    state["spent"] += c
    state["log"].append({
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": label, "model": model, "usd": round(c, 4),
        "spent_total": round(state["spent"], 4),
    })
    save_state(state)
    print(f"    · {label}: ${c:.3f}  (running total ${state['spent']:.2f})")


# ------------------------------------------------------------- budget checkpoint
def budget_gate(state: dict, budget: float, auto_yes: bool) -> bool:
    """Return True to proceed, False to stop. Asks the user at the half-budget mark."""
    if state["spent"] >= budget:
        print(f"\n🛑 HARD STOP — spent ${state['spent']:.2f} ≥ budget ${budget:.2f}. "
              f"Raise --budget to continue.")
        return False
    half = budget * CHECKPOINT_FRAC
    if state["spent"] >= half and not state["checkpoint_ack"]:
        print(textwrap.dedent(f"""
            ⏸  HALF-BUDGET CHECKPOINT
               Spent ${state['spent']:.2f} of ${budget:.2f} ({CHECKPOINT_FRAC*100:.0f}% = ${half:.2f}).
               Completed stages: {sorted(k for k,v in state['stages'].items() if v.get('done'))}
        """))
        if auto_yes:
            print("    --yes set: continuing past the checkpoint.")
        else:
            ans = input("   Continue researching? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("   Stopping at your request. Re-run later to resume.")
                return False
        state["checkpoint_ack"] = True      # only ask once
        save_state(state)
    return True


# --------------------------------------------------------------- Claude helpers
def _text_and_urls(resp):
    """Pull the assistant text and any cited/searched URLs out of a response."""
    parts, urls = [], []
    for block in resp.content:
        if block.type == "text":
            parts.append(block.text)
            for cit in (getattr(block, "citations", None) or []):
                u = getattr(cit, "url", None)
                if u:
                    urls.append(u)
        elif block.type == "web_search_tool_result":
            for r in (getattr(block, "content", None) or []):
                u = getattr(r, "url", None)
                if u:
                    urls.append(u)
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); uniq.append(u)
    return "\n".join(parts).strip(), uniq


def research(client, model, style, prompt, focus=None):
    """One deep research call with web search enabled."""
    sys_prompt = (
        "You are a meticulous research librarian building an Obsidian knowledge vault.\n"
        + style +
        "\nSearch the web thoroughly before writing. Prefer primary and scholarly sources. "
        "Cite as you go. Output clean Obsidian markdown (no code fences around the whole "
        "note). Use [[wiki-links]] for cross-references and an explicit ## Sources section."
    )
    user = prompt if not focus else (
        prompt + "\n\nFOCUS THIS PASS only on filling these gaps:\n- " + "\n- ".join(focus)
    )
    resp = client.messages.create(
        model=model, max_tokens=8000, system=sys_prompt,
        tools=[{"type": "web_search_20250305", "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES}],
        messages=[{"role": "user", "content": user}],
    )
    return resp, _text_and_urls(resp)


def critique(client, model, checklist, draft):
    """Check a draft against the checklist; return (complete, gaps[])."""
    cl = "\n".join(f"- {c}" for c in checklist)
    resp = client.messages.create(
        model=model, max_tokens=1000,
        system="You are a strict completeness reviewer. Reply with ONLY a JSON object.",
        messages=[{"role": "user", "content":
            f"Checklist the draft must satisfy:\n{cl}\n\n"
            f"DRAFT:\n{draft[:60000]}\n\n"
            'Reply JSON: {"complete": bool, "gaps": [short missing-item strings]}. '
            "gaps = concrete things to research next; [] if solid."}],
    )
    txt = "".join(b.text for b in resp.content if b.type == "text").strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1]
    try:
        data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        return bool(data.get("complete")), list(data.get("gaps", []))[:6], resp
    except Exception:
        return True, [], resp     # don't block on a parse failure


# ------------------------------------------------------------------- write note
def write_note(stage, body, urls):
    out = VAULT / stage["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    fm = textwrap.dedent(f"""\
        ---
        tags: [yoga, {stage['id']}]
        title: "{stage['title']}"
        generated: {datetime.date.today().isoformat()}
        pipeline_stage: {stage['id']}
        ---

        """)
    src = ""
    if urls:
        src = "\n\n## Source URLs (auto-collected)\n" + "\n".join(f"- {u}" for u in urls)
    out.write_text(fm + body + src + "\n")
    return out


# ----------------------------------------------------------- media auto-download
def media_manifest(client, model, note_text):
    """Ask the model to distil the media note into a strict JSON manifest of
    CONFIRMED open-licence items. Returns a list of dicts."""
    resp = client.messages.create(
        model=model, max_tokens=4000,
        system="You extract a clean JSON media manifest. Reply with ONLY a JSON array.",
        messages=[{"role": "user", "content":
            "From this media note, return ONLY items whose licence is explicitly an "
            "OPEN licence (Public Domain / CC0 / CC-BY / CC-BY-SA / Wikimedia / "
            "Internet Archive public). Output a JSON array of objects with keys: "
            '"title","url","source","licence","attribution","illustrates". The "url" '
            "must be a DIRECT link to the media file where possible. Omit anything "
            "whose licence is unclear.\n\nNOTE:\n" + note_text[:60000]}],
    )
    txt = "".join(b.text for b in resp.content if b.type == "text").strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1]
    try:
        return json.loads(txt[txt.find("["): txt.rfind("]") + 1]), resp
    except Exception:
        return [], resp


def _safe_name(url, idx):
    base = unquote(os.path.basename(urlparse(url).path)) or f"item-{idx}"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.") or f"item-{idx}"
    return f"{idx:02d}-{base}"[:120]


def download_media(items):
    """Fetch each manifest item into 90-Assets/. Verifies content-type + size,
    writes a .txt sidecar with licence/attribution, and a manifest.json. Returns a
    summary dict. Pure stdlib (urllib); no model calls, no spend."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    saved, skipped = [], []
    for i, it in enumerate(items, 1):
        url = (it.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            skipped.append({**it, "reason": "no direct url"}); continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
                clen = int(r.headers.get("Content-Length") or 0)
                if clen and clen > MEDIA_MAX_BYTES:
                    skipped.append({**it, "reason": f"too big ({clen} B)"}); continue
                if ctype and not ctype.startswith(MEDIA_OK_TYPES):
                    # likely an HTML description page, not the file itself
                    skipped.append({**it, "reason": f"not a media file ({ctype})"}); continue
                data = r.read(MEDIA_MAX_BYTES + 1)
            if len(data) > MEDIA_MAX_BYTES:
                skipped.append({**it, "reason": "too big (stream)"}); continue
            name = _safe_name(url, i)
            if "." not in name:
                ext = mimetypes.guess_extension(ctype or "") or ""
                name += ext
            path = ASSETS_DIR / name
            path.write_bytes(data)
            (ASSETS_DIR / (name + ".txt")).write_text(textwrap.dedent(f"""\
                title:       {it.get('title','')}
                source:      {it.get('source','')}
                source_url:  {url}
                licence:     {it.get('licence','')}
                attribution: {it.get('attribution','')}
                illustrates: {it.get('illustrates','')}
                """))
            saved.append({**it, "file": name, "bytes": len(data)})
            print(f"      ↓ {name}  ({len(data)//1024} KB)")
        except Exception as e:
            skipped.append({**it, "reason": f"{type(e).__name__}: {e}"})
    (ASSETS_DIR / "manifest.json").write_text(
        json.dumps({"saved": saved, "skipped": skipped}, indent=2, ensure_ascii=False))
    print(f"    ↓ media: {len(saved)} saved, {len(skipped)} skipped "
          f"→ 90-Assets/ (manifest.json)")
    return {"saved": len(saved), "skipped": len(skipped)}


# -------------------------------------------------------------------------- run
def main():
    ap = argparse.ArgumentParser(description="Yoga Atlas deep-research pipeline")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET,
                    help=f"USD cap (asks at half). default {DEFAULT_BUDGET}")
    ap.add_argument("--research-model", default=DEFAULT_RESEARCH_MODEL)
    ap.add_argument("--critic-model", default=DEFAULT_CRITIC_MODEL)
    ap.add_argument("--only", help="run a single stage id")
    ap.add_argument("--force", action="store_true", help="re-run completed stages")
    ap.add_argument("--yes", action="store_true", help="skip the half-budget prompt")
    ap.add_argument("--reset-budget", action="store_true",
                    help="clear the checkpoint ack (e.g. after raising --budget)")
    ap.add_argument("--no-download-media", action="store_true",
                    help="don't auto-download files for media stages")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first:  export ANTHROPIC_API_KEY=sk-ant-...")

    plan = yaml.safe_load(PLAN_PATH.read_text())
    style = plan.get("style_notes", "")
    stages = plan["stages"]
    if args.only:
        stages = [s for s in stages if s["id"] == args.only] or sys.exit(
            f"No stage id '{args.only}'")

    state = load_state()
    if args.reset_budget:
        state["checkpoint_ack"] = False; save_state(state)
    client = anthropic.Anthropic()

    print(f"Yoga Atlas pipeline · budget ${args.budget:.0f} "
          f"(checkpoint ${args.budget*CHECKPOINT_FRAC:.0f}) · already spent "
          f"${state['spent']:.2f}\nResearch={args.research_model}  "
          f"Critic={args.critic_model}\n" + "-" * 64)

    for stage in stages:
        sid = stage["id"]
        if state["stages"].get(sid, {}).get("done") and not args.force:
            print(f"✓ {sid} — already done (skip; --force to redo)")
            continue
        if not budget_gate(state, args.budget, args.yes):
            break

        print(f"\n▶ {sid}  {stage['title']}")
        resp, (body, urls) = research(client, args.research_model, style, stage["prompt"])
        record(state, args.research_model, resp.usage, f"{sid} research")

        for rnd in range(MAX_GAPFILL_ROUNDS):
            if not budget_gate(state, args.budget, args.yes):
                break
            complete, gaps, cresp = critique(client, args.critic_model,
                                             stage["checklist"], body)
            record(state, args.critic_model, cresp.usage, f"{sid} critique r{rnd+1}")
            if complete or not gaps:
                print(f"    ✓ checklist satisfied")
                break
            print(f"    ↻ gaps: {gaps}")
            resp, (more, murls) = research(client, args.research_model, style,
                                           stage["prompt"], focus=gaps)
            record(state, args.research_model, resp.usage, f"{sid} gapfill r{rnd+1}")
            body += "\n\n<!-- gap-fill pass -->\n\n" + more
            urls += [u for u in murls if u not in urls]

        out = write_note(stage, body, urls)
        rec = {"done": True, "out": str(out.relative_to(VAULT)), "urls": len(urls)}
        print(f"    → wrote {out.relative_to(VAULT)}  ({len(urls)} source urls)")

        # Auto-download media for stages flagged `download: true`.
        if stage.get("download") and not args.no_download_media:
            items, mresp = media_manifest(client, args.critic_model, body)
            record(state, args.critic_model, mresp.usage, f"{sid} media-manifest")
            print(f"    · media manifest: {len(items)} open-licence items")
            if items:
                rec["media"] = download_media(items)

        state["stages"][sid] = rec
        save_state(state)

    done = sorted(k for k, v in state["stages"].items() if v.get("done"))
    print("\n" + "-" * 64 + f"\nDone {len(done)}/{len(plan['stages'])} stages · "
          f"spent ${state['spent']:.2f}/${args.budget:.0f}\nStages: {done}")


if __name__ == "__main__":
    main()
