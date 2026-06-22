# Yoga Atlas — research pipeline

A standalone Python pipeline that builds the [[Yoga Atlas]] vault by running Claude
on a deep-research plan, stage by stage, with completeness checks and a budget guard.
It is **not** a Claude Code skill or hook — just a script you run yourself.

## What it does

For each stage in `plan.yaml`:

1. **Research** — Claude + web search produces a deeply-sourced Obsidian note.
2. **Critique** — a second (cheaper) Claude call checks the draft against that
   stage's checklist and returns concrete **gaps**.
3. **Gap-fill** — if gaps remain, a focused follow-up research pass is merged in
   (up to `MAX_GAPFILL_ROUNDS`).
4. **Write** — the note lands in the right vault folder (e.g. `30-Asanas/…`).

Progress + spend are saved in `state.json`, so re-running **resumes**. The script
**stops and asks you** once it has spent **half** the budget, and **hard-stops** at
the full budget.

## Setup

```bash
pip install anthropic pyyaml
export ANTHROPIC_API_KEY=sk-ant-...        # your own key (separate billing)
```

## Run

```bash
cd ~/projects/yoga-atlas/research
python3 research_pipeline.py                       # all stages, default $50 budget
python3 research_pipeline.py --budget 50           # asks you at $25
python3 research_pipeline.py --research-model claude-sonnet-4-6   # cheaper/faster
python3 research_pipeline.py --only 50-asanas      # one stage
python3 research_pipeline.py --force               # redo completed stages
python3 research_pipeline.py --yes                 # don't pause at the checkpoint
```

After raising the budget to keep going past a stop:

```bash
python3 research_pipeline.py --budget 100 --reset-budget
```

## Knobs (top of `research_pipeline.py`)

| Constant | Meaning |
|---|---|
| `DEFAULT_BUDGET` | USD cap; halts for confirmation at half |
| `CHECKPOINT_FRAC` | fraction of budget that triggers the pause (0.5) |
| `DEFAULT_RESEARCH_MODEL` / `DEFAULT_CRITIC_MODEL` | models used |
| `MAX_GAPFILL_ROUNDS` | follow-up passes per stage |
| `WEB_SEARCH_MAX_USES` | searches Claude may run per call |
| `PRICING` / `WEB_SEARCH_USD_PER_CALL` | cost model — **estimates, edit to match** |

## Notes & caveats

- **Cost is estimated** from token usage + web-search count using the `PRICING`
  table. Treat the running total as a close guide, not your invoice — verify
  against the Anthropic console.
- Edit `plan.yaml` freely: add/remove stages, sharpen prompts, tighten checklists.
- Media stage collects **open-licence** links only (PD/CC/Wikimedia/Archive).
  Downloading the files is intentionally left manual (review licences first).
- Re-runs skip finished stages; delete a stage's entry in `state.json` (or use
  `--only … --force`) to redo just that one.
