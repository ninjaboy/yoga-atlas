---
tags: [yoga, 90-media]
title: "Open-licence images & video"
generated: 2026-06-22
---

# 🖼️ Open-Licence Media Library

Sourced, **open-licence only** (Public Domain / CC0 / CC-BY[-SA] / Wikimedia / Internet
Archive). Each item lists its repository, licence and attribution, and which note it
illustrates. **Always re-confirm the per-file licence** on the source page before reuse —
repository *categories* mix licences even when most items are open.

> ⚠️ **Copyright caution:** most **20th-century photographs** of the great modern teachers
> (Krishnamacharya, Iyengar, Jois, etc.) are **still in copyright** and are deliberately
> **excluded** here. Use portraits only where a specific PD/CC release is confirmed.

## Historical manuscript illustrations (Public Domain by age)

| Item | Source / repository | Date | Licence | Illustrates |
|---|---|---|---|---|
| **Joga Pradīpikā** — āsana & mudrā plates | British Library, via [Public Domain Review](https://publicdomainreview.org/collection/hatha-yoga-images-from-the-joga-pradipika) (CDN: `pdr-assets.b-cdn.net/collections/hatha-yoga-images-from-the-joga-pradipika/…`) | 18th–19th c. | **PD Worldwide** | [[Foundational-Texts]], [[Asana-Catalogue]] |
| **Sritattvanidhi** — 122 posture plates | Mysore Palace ms.; reproductions via [Open Culture](https://www.openculture.com/2021/05/beautiful-19th-century-indian-drawings-show-hatha-yoga-poses.html) / Wikimedia | 19th c. | **PD (age)** | [[Asana-Catalogue]], [[History-and-Origins]] |
| **Bahr al-ḥayāt** ("Ocean of Life") — illustrated āsanas | Mughal ms. (comm. Jahāngīr); reproductions on Wikimedia | 16th c. | **PD (age)** | [[Foundational-Texts]] |

## Wikimedia Commons categories (per-file licence — verify each)

| Category | URL | Notes |
|---|---|---|
| **Category:Yoga** | https://commons.wikimedia.org/wiki/Category:Yoga | broad; iconography, diagrams, photos |
| **Category:Asana** | https://commons.wikimedia.org/wiki/Category:Asana | posture photos & plates |
| Wikipedia PD image resources | https://en.wikipedia.org/wiki/Wikipedia:Public_domain_image_resources | index of PD repositories |

## Iconography (look for PD/CC releases on Commons)
- **Patañjali** as part-serpent (Ādiśeṣa) — temple murals / line art on Wikimedia (many PD). → [[Key-Figures]]
- **Śiva as Ādiyogi / Naṭarāja** — abundant PD art on Wikimedia. → [[History-and-Origins]]
- **Chakra & subtle-body diagrams** — many CC-BY/CC0 diagrams on Commons. → [[Philosophy-and-Concepts]]

## Video (open / official)
- **Internet Archive** ([archive.org](https://archive.org)) — search "yoga" filtered to PD /
  CC; holds early instructional and newsreel footage (per-item licence varies).
- **Wikimedia Commons** video category — CC-licensed demonstration clips.
- *(Confirm licence per file; many YouTube uploads are All-Rights-Reserved and excluded.)*

## For the auto-downloader
`research_pipeline.py` (stage `90-media`, `download: true`) distils this note into a JSON
manifest and pulls the **confirmed-open** files into [[../90-Assets/]] with a `.txt` licence
sidecar each and a `manifest.json`. Page URLs that resolve to HTML (e.g. a Commons *file
description* page) are skipped with a note — replace them with the **direct file URL**
(`Special:FilePath/…` or the media CDN link) to fetch the actual image.

## Sources
- [Hatha Yoga images from the Joga Pradīpikā — Public Domain Review](https://publicdomainreview.org/collection/hatha-yoga-images-from-the-joga-pradipika)
- [19th-c. Hatha Yoga drawings — Open Culture](https://www.openculture.com/2021/05/beautiful-19th-century-indian-drawings-show-hatha-yoga-poses.html)
- [Category:Yoga — Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Yoga)
- [Category:Asana — Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Asana)
- [Public domain image resources — Wikipedia](https://en.wikipedia.org/wiki/Wikipedia:Public_domain_image_resources)
