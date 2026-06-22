# 🧘 Yoga Atlas

A sourced, open-licence knowledge vault on **yoga** — history, traditions, texts,
figures, asanas, practices, philosophy, modern styles, and an open-media library —
built in the spirit of the [[demonology]] vault: careful, cited, respectful of a
living tradition, and illustrated only with Public-Domain / Creative-Commons media.

## Layout (Obsidian vault)

| Folder | Contents |
|---|---|
| `00-Maps/` | Top-level overview & concept maps |
| `10-Traditions/` | History, origins, the classical paths & lineages |
| `20-Schools/` | Modern transnational styles |
| `30-Asanas/` | Posture catalogue |
| `40-Texts/` | Foundational source literature |
| `50-Figures/` | Key people, classical → modern |
| `60-Concepts/` | Philosophy & core concepts |
| `70-Practices/` | Pranayama, kriyas, meditation, subtle body |
| `80-Media/` | Open-licence image & video library (URLs + licences) |
| `90-Assets/` | Downloaded media files (after manual licence review) |
| `research/` | The pipeline that generates the notes (`research_pipeline.py`, `plan.yaml`) |

## How it's built

The notes are produced by a standalone deep-research pipeline — see
[`research/README.md`](research/README.md). It runs Claude on the plan in
`research/plan.yaml`, checks each draft for gaps and re-researches them, and pauses
to ask before spending more than half the budget.

## Conventions

- **Sourced only** — every non-obvious claim gets a citation.
- **Open media only** — PD/CC/Wikimedia/Internet Archive, with attribution.
- **Respectful framing** — separate historical, philosophical, and modern-commercial
  threads without sneering; flag contested claims.
