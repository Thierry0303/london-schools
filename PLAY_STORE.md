# Publishing London Schools Directory to the Google Play Store

This repo is now set up as an **installable PWA**, which is the foundation for a
**Trusted Web Activity (TWA)** — a thin native Android app that wraps
`https://londonschool.directory` and can be listed on the Google Play Store.
There is **no separate app codebase**: the app *is* the website, so every future
site update ships to the app automatically once published.

## What was added to this repo

| File | Purpose |
|------|---------|
| `manifest.webmanifest` | Web App Manifest — app name, icons, colours, `display: standalone` |
| `icons/` | App icons: 192/512 (`any`) + 192/512 (`maskable`) + Apple touch icon |
| `sw.js` | Service worker — offline support (required for install quality) |
| `offline.html` | Branded fallback page shown when the device is offline |
| `.well-known/assetlinks.json` | Digital Asset Links — proves the site and app belong together (removes the browser URL bar). **Needs your app's signing fingerprint — see step 3.** |
| `vercel.json` | Serves the manifest, `sw.js` and `assetlinks.json` with correct headers |
| HTML pages + `scripts/build_school_pages.py` | Manifest link + service-worker registration added to all pages (generated school pages pick it up on the next monthly rebuild) |

**Chosen Android package name:** `directory.londonschool.twa`
(reverse of the domain — keep this exact value everywhere below).

---

## Step 1 — Deploy the PWA changes

Merge this branch to `main`. Vercel auto-deploys. Then confirm these all load:

- https://londonschool.directory/manifest.webmanifest
- https://londonschool.directory/sw.js
- https://londonschool.directory/.well-known/assetlinks.json  *(will still have a placeholder fingerprint — that's expected until step 3)*

Optional check: open the site in Chrome → DevTools → **Application → Manifest**.
It should show the icons and "Installability: no issues".

## Step 2 — Generate the Android app package with PWABuilder

1. Go to **https://www.pwabuilder.com** and enter `https://londonschool.directory`.
2. It scores the PWA (manifest / service worker / security) — all should be green.
3. Click **Package for stores → Android → Google Play**.
4. Set:
   - **Package ID:** `directory.londonschool.twa`
   - **App name:** London Schools Directory
   - **Signing key:** choose **"Create new"** (recommended). PWABuilder generates a
     keystore and shows you its details.
5. Download the ZIP. It contains:
   - `app-release-bundle.aab` — upload this to Play Console
   - `signing.keystore` + a `signing-key-info.txt` (**password + key alias**)
   - an `assetlinks.json` with your real SHA-256 fingerprint

> ⚠️ **Back up the keystore and its passwords somewhere safe and private.**
> If you lose them you cannot ship updates to the same app. Never commit them to git.

## Step 3 — Wire up Digital Asset Links

1. Open the `assetlinks.json` that PWABuilder produced and copy the
   `sha256_cert_fingerprints` value (looks like `AB:CD:12:...`).
2. Paste it into this repo's `.well-known/assetlinks.json`, replacing
   `REPLACE_WITH_YOUR_PLAY_APP_SIGNING_SHA256_FINGERPRINT`.
3. Commit + push so Vercel serves the real fingerprint.

> If you later enable **Play App Signing** (default for new apps), Google re-signs
> the app with *its own* key. After your first upload, go to
> **Play Console → your app → Setup → App integrity → App signing** and add the
> **"App signing key certificate" SHA-256** to `assetlinks.json` as a *second*
> entry (both fingerprints can coexist in the array). This is what stops the
> URL bar from showing in the installed app.

## Step 4 — Publish on Google Play Console (account: `thierry03`)

1. Sign in at **https://play.google.com/console**. If this is a brand-new
   developer account there's a **one-time $25 fee** and an identity check.
2. **Create app** → name "London Schools Directory", type *App*, *Free*.
3. Upload `app-release-bundle.aab` under **Production** (or start with
   **Internal testing** to trial it on your own device first — recommended).
4. Complete the required listing items:
   - Short + full description (pull from `README.md`)
   - **Feature graphic** 1024×500, **phone screenshots** (2+), app icon 512×512
     (you can reuse `icons/icon-512.png`)
   - **Privacy policy URL** (Play requires one — add a `/privacy` page to the site
     if you don't have one yet)
   - Content rating questionnaire, Data safety form, target audience
5. Submit for review. First review typically takes a few days.

## Step 5 — Verify after launch

- Install the app from Play on an Android device.
- Confirm it opens **full-screen with no browser address bar** (this only works
  once step 3's fingerprint is live — recheck `assetlinks.json` if you still see a bar).
- Turn on airplane mode and reopen → you should see the branded offline page.

---

### Notes
- Updating the website updates the app content instantly — you only rebuild/re-upload
  the `.aab` when you change the app's *shell* (name, icon, package config).
- iOS: TWAs are Android-only. iPhone users can still **Add to Home Screen** from
  Safari and get the standalone PWA experience thanks to the manifest + Apple touch icon.
