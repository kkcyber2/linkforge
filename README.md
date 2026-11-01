# linkforge

[![tests](https://github.com/kkcyber2/linkforge/actions/workflows/tests.yml/badge.svg)](https://github.com/kkcyber2/linkforge/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Short links with click analytics that are actually readable — referrers bucketed
into channels, devices classified, and no way to turn the service into an open
redirector.

```bash
pip install -r requirements.txt
uvicorn linkforge.app:app --port 8080
```

```bash
curl -X POST localhost:8080/api/links -H 'content-type: application/json' \
  -d '{"target":"https://example.com/pricing","slug":"pricing"}'
# -> {"slug":"pricing","target":"https://example.com/pricing","clicks":0,"active":true}

curl -i localhost:8080/pricing          # 302 to the target, click recorded
curl localhost:8080/api/links/pricing/stats
# -> {"clicks":1,"by_referrer":{"linkedin":1},"by_device":{"mobile":1},...}
```

## The security decision

**Only `http` and `https` targets are accepted.** A shortener that redirects to
whatever it is given is an open redirector, and `javascript:` / `data:` targets
make it a stored XSS vector on your own domain. `validate_target` rejects them
and `test_rejects_dangerous_schemes` covers seven attack strings.

## The analytics decision

**302, never 301.** A permanent redirect is cached by the browser, so that
visitor never hits your server again and you lose their clicks forever. This is
the single most common way a link shortener silently under-reports.

**Referrers are bucketed, not stored raw.** `https://www.linkedin.com/feed/?trk=...`
becomes `linkedin`. A report of raw URLs is unreadable; a report of channels is
a decision.

## Design decisions

**Reserved slugs.** `api`, `admin`, `healthz`, `static`, `assets`, `login`,
`signup` can never be issued, or a link would shadow a real route.

**Collision-safe generation.** 7 chars of base62 with a retry loop against the
existing set — `test_generated_slugs_unique` creates 300 and asserts 300 distinct.

**Deactivation, not deletion.** Old links keep their click history; they just
stop resolving.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/links` | Create |
| GET | `/api/links` | List |
| GET | `/api/links/{slug}/stats` | Click breakdown |
| DELETE | `/api/links/{slug}` | Deactivate |
| GET | `/{slug}` | 302 redirect + record click |
| GET | `/healthz` | Liveness |

## Tests

```bash
python -m pytest -q     # 47 passed
```

## Limitations — read this

- **In-memory.** Restart and every link is gone. Swap `LinkStore` for a table.
- **No auth.** Anyone who can reach `/api/links` can create links on your domain.
- **No bot filtering in the counts.** Bots are classified as `bot` in `by_device`
  but still counted in `clicks` — filter them in your report.
- **No UTM parsing.** Referrer only; campaign parameters are not extracted.
- **No rate limiting.** A link hammered in a loop will grow its click list
  unbounded. Add a cap or a counter before production.

## License

MIT — see [LICENSE](LICENSE).
