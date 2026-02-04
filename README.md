# Site Change Monitor (Lite)

This ZIP gives you a **one-click GitHub Actions** tool that checks **one web page** and publishes a simple report to a **GitHub Pages URL**.

Features (Lite)
- Monitor **1 URL** (manual run)
- Detects changes by comparing the latest content to the previous run
- Publishes a clean report to GitHub Pages (**main / root**)
- Stores the last snapshot in your repo so the next run can compare

Limitations (Lite)
- Manual runs only (no schedule)
- 1 URL only
- No multi-page dashboards, no notifications

## Quick start (GitHub only)
1) Unzip this package
2) Upload ALL files to your repository **root**
3) Copy `config.example.json` → `config.json` and edit your `target_url`
4) Set up GitHub Pages (main / root)
5) Add the workflow file (copy-paste)
6) Run the workflow → open your Pages URL

## GitHub Pages setup
1) Open your repo on GitHub
2) Go to **Settings → Pages**
3) Under **Build and deployment**:
   - **Source**: Deploy from a branch
   - **Branch**: `main`
   - **Folder**: `/(root)`
4) Click **Save**
5) Your Pages URL will appear on the same screen (it may take 1–3 minutes)

## GitHub Actions setup

File name (create this file on GitHub):

`.github/workflows/run.yml`

How to add (GitHub UI):
1) Open your repository on GitHub
2) Click **Add file → Create new file**
3) In the filename box, paste exactly:
   `.github/workflows/run.yml`
4) Paste the YAML below into the editor
5) Click **Commit changes** (commit to your default branch)

Workflow YAML (copy-paste):

```yaml
name: Run Site Change Monitor (Lite)

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true

      - name: Selftest
        run: python main.py --selftest

      - name: Generate report
        run: python main.py

      - name: Commit & push output
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          # Only stage what this tool generates
          git add index.html sitemap.xml robots.txt assets data/state.json

          git diff --cached --quiet && echo "No changes" && exit 0
          git commit -m "Update monitor report [skip ci]"
          git push
```

## How to run
1) Go to **Actions** tab
2) Click **Run Site Change Monitor (Lite)**
3) Click **Run workflow**
4) Wait for the run to finish (green check)

## Where to see the site (URL)
Go to **Settings → Pages** and open the URL shown there.

## Troubleshooting

No “Run workflow” button:
- The workflow file is not on the default branch
- `workflow_dispatch` is missing or YAML indentation is broken
- The file path is not exactly `.github/workflows/run.yml`

Pages shows 404 or old content:
- Confirm **Settings → Pages** is set to **main / (root)**
- Wait 1–3 minutes for Pages to update
- Re-run the workflow once to ensure `index.html` exists at repo root

Commit/push failed:
- Ensure the workflow includes `permissions: contents: write`
- Ensure the repository is not set to “Read-only” for Actions
