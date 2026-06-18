# Strategy template

Copy this folder when starting a new strategy so every strategy in the repo looks the same and your
reviewer always knows where to look. Rename the copy to the next number, e.g. `02-my-new-strategy/`
(lowercase, hyphens, **no spaces** — spaces break GitHub links).

## Standard layout

```
NN-strategy-name/
├── README.md          ← friendly landing page (see required top section below)
├── REPORT.md          ← the full write-up; image links point at outputs/run1/<chart>.png
├── outputs/run1/      ← the reference run that ships with the repo: charts (.png),
│                        metrics.csv / metrics.md, run_config.json. THIS GETS COMMITTED.
├── requirements.txt   ← dependencies, so others can run it
└── <code>/            ← the runnable program (package, scripts, configs, tests)
```

## Every README.md must start with these reviewer-facing pieces (in this order)

1. **Title + one-paragraph plain-English summary** — what the strategy does, no jargon.
2. **Link to the full report:** `**📄 [Read the full report → REPORT.md](REPORT.md)**`
3. **The main chart, embedded:** `![Equity curves](outputs/run1/equity_curves.png)`
4. **Headline metrics table** — paste from `outputs/run1/metrics.md` and add a one-line legend.
5. **"Want to run it yourself?"** — the short copy-paste command-line steps.

Put detailed technical / install content *below* a `## Technical reference` heading.

## Don't forget

- Add a row to the **repo-root [README.md](../README.md)** Strategies table linking to your report.
- Image links in `REPORT.md` must be **`outputs/run1/<name>.png`** (not bare names) so they render
  on GitHub.
- Keep secrets out: use a `.env.example`, never commit real keys (the root `.gitignore` handles this).
