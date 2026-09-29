# Network probe results

- Date: 2026-09-29
- Environment id: env_01LxHPwdUPcgb11yFs4hmKGN
- Method: `curl -sS -o /dev/null -m 15 -w '%{http_code}' -L <url>` through the session's agent proxy

| URL | HTTP status | Result |
| --- | --- | --- |
| https://whop.com/discover/ | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://whop.com/content-rewards/ | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://huggingface.co | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://drive.google.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://next.frame.io | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://we.tl | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://www.youtube.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://memecpm.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://katieglows.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://discord.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://www.tiktok.com | 000 | blocked: CONNECT tunnel failed, proxy answered 403 |
| https://pypi.org | 200 | reachable (pypi.org is on the proxy's noProxy list, direct egress) |
| https://github.com | 400 | reachable via proxy, but plain GET to the site root returns 400 (git operations go through the proxy's git config injection) |

## Proxy status (`$HTTPS_PROXY/__agentproxy/status`)

- enabled: true, port 37449, selective: false, standalone: false, toolScoped: false
- bundleCoversEveryHost: true, gitConfigInjection: true, gitSshRewrite: true
- noProxy includes: api.anthropic.com, mcp-proxy.anthropic.com, registry.npmjs.org, jsr.io, pypi.org, files.pythonhosted.org, index.crates.io, proxy.golang.org, private ranges
- recentRelayFailures: `connect_rejected` for whop.com:443, huggingface.co:443 and the other blocked hosts above, detail "gateway answered 403 to CONNECT (policy denial or upstream failure)"

## Package and model downloads

| Check | Result |
| --- | --- |
| `pip download faster-whisper --no-deps -d /tmp/x -q` | PIP_OK (PyPI wheel download works) |
| `curl -L https://huggingface.co/Systran/faster-whisper-small/resolve/main/config.json` | 000, CONNECT tunnel failed, proxy 403 (model weights cannot be fetched from Hugging Face in this environment) |

## Summary

Only PyPI (direct) and github.com (via proxy) are reachable. Every other probed host, including huggingface.co, drive.google.com, youtube.com, discord.com and tiktok.com, is denied by the environment's network policy at the CONNECT stage. Installing faster-whisper from PyPI works, but downloading Whisper model weights from Hugging Face does not.
