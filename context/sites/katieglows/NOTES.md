# katieglows.com — capture notes

**Status: SITE UNREACHABLE FROM THIS ENVIRONMENT. Nothing was captured.**

Attempted 2026-09-29T12:31:57Z from a Claude Code cloud session.

## What was tried

1. `curl -L https://katieglows.com and https://katieglows.com/method` through the session's agent proxy.
   Result: `curl: (56) CONNECT tunnel failed, response 403`.
   The proxy status endpoint recorded the reason as
   `connect_rejected — gateway answered 403 to CONNECT (policy denial)` for `katieglows.com:443`.
2. Claude's WebFetch tool (runs outside the container).
   Result: `EGRESS_BLOCKED — Access to katieglows.com is blocked by the network egress proxy.`
3. Playwright/Chromium was not attempted because it uses the same proxy and would hit the same denial.

No third-party mirrors or archives were used, so nothing here should be mistaken for the live site.

## What this means

The Claude Code cloud environment's **Network access** policy does not allow `katieglows.com`.
This is an environment setting, not a problem with the site itself.

## How to unblock

In the Claude Code web app: open the cloud environment menu in the session title bar → **Edit** →
**Network access** → either choose a broader access level or add `katieglows.com` (and `www.katieglows.com`) to
the allowed domains. Access levels are described at
https://code.claude.com/docs/en/claude-code-on-the-web

Then re-run the capture task. Expected outputs in this folder once it succeeds:

- `<slug>.html` raw HTML per page (homepage = `index`)
- `<slug>_desktop.png` (1280 wide, full page) and `<slug>_mobile.png` (390 wide, full page)
- `<slug>.md` transcription of all visible text in order
- This file filled in with: tech stack signals (meta generator, framework, hosting hints such as
  Framer/Webflow/Wix/Carrd/Shopify/WordPress/Next), fonts, colours, forms and their submit targets,
  page-load notes, exactly what /method sells (product name, price, format, promises, sections), and whether the site already has a blog/article section.

## Alternative if the policy cannot be changed

Capture the pages from a machine that can reach the site (browser "Save page as…", full-page
screenshots via DevTools or a browser extension) and commit them into this folder with the layout above.
