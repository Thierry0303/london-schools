name: Monthly Data Refresh
on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 15 * *'   # 6am on the 15th of every month
permissions:
  contents: write
jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 35
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install requests pandas numpy pyyaml odfpy --break-system-packages -q
      # Step 1: Test BEFORE refresh — confirm site is healthy going in
      - name: Pre-refresh tests
        run: python3 scripts/test_site.py
        continue-on-error: true   # Don't block refresh if pre-tests fail
      # Step 2: Refresh data from all official sources
      - name: Refresh data
        run: python3 scripts/refresh_data.py
      # Step 2b: Fetch independent school ratings from DfE CSV
      - name: Fetch independent school ratings
        run: python3 scripts/fetch_independent_ratings.py
        continue-on-error: true   # Don't block build if DfE CSV is temporarily unavailable
      # Step 2c: Fetch independent school enrichment data
      - name: Fetch independent school enrichment data
        run: python3 scripts/fetch_independent_school_data.py
        continue-on-error: true   # Don't block if CSV missing or has issues
      # Step 2d: AI-agent enrichment (fees, catchment distance, etc. from official sources)
      - name: AI-agent enrichment
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AGENT_MAX_PER_RUN: "40"
        run: python3 scripts/agent_enrich.py
        continue-on-error: true   # Non-fatal: only writes verified, sourced values; skips if no key
      # Step 3: Build pages FIRST, from the freshly-refreshed data
      - name: Build static pages
        run: |
          python3 scripts/build_school_pages.py
          echo "$(date -u)" > schools/.last_built
      # Step 3b: Build borough hub pages
      - name: Build borough hub pages
        run: python3 scripts/build_borough_hubs.py
      # Step 4: Test AFTER rebuild — validates the freshly-built pages; abort if broken
      - name: Post-refresh tests
        id: post_test
        run: python3 scripts/test_site.py
      # Step 5: Commit everything (only if tests passed)
      - name: Commit and push
        if: steps.post_test.outcome == 'success'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A schools.json schools/ sitemap_data.txt robots.txt data/
          git commit --allow-empty -m "chore: data refresh $(date +'%Y-%m')"

          # Built pages are DERIVED artifacts. On divergence the freshly-built
          # local version must win — never rebase/merge generated HTML (identical
          # files regenerated on both sides produce endless conflicts).
          for attempt in 1 2 3 4 5; do
            if git push origin HEAD:main; then
              echo "Pushed on attempt $attempt"
              exit 0
            fi
            echo "Push $attempt rejected — integrating remote, keeping locally-built pages..."
            git fetch origin main
            if ! git rebase -X ours origin/main; then
              echo "Conflicts during rebase — forcing local build to win"
              git checkout --ours -- . 2>/dev/null || true
              git add -A
              GIT_EDITOR=true git rebase --continue 2>/dev/null || git rebase --abort 2>/dev/null || true
              git reset --soft origin/main
              git add -A schools.json schools/ sitemap_data.txt robots.txt data/
              git commit --allow-empty -m "chore: data refresh $(date +'%Y-%m')"
            fi
            sleep $((attempt * 3))
          done
          echo "::error::Could not push after 5 attempts"
          exit 1
      # Step 6: If post-refresh tests failed — restore previous schools.json
      - name: Restore previous data on failure
        if: steps.post_test.outcome == 'failure'
        run: |
          echo "⚠️ Post-refresh tests failed — restoring previous schools.json"
          git checkout HEAD -- schools.json
          echo "✅ Previous data restored — site unchanged"
