"""FastAPI app: create links, redirect with analytics, read stats."""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from .core import LinkStore

app = FastAPI(title="linkforge", version="1.0.0")
store = LinkStore()


class CreateLink(BaseModel):
    target: str
    slug: str | None = None
    title: str = ""


@app.get("/healthz")
def healthz():
    return {"status": "ok", "links": len(store.all())}


@app.post("/api/links")
def create(body: CreateLink):
    try:
        link = store.create(body.target, body.slug, body.title)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return link.as_dict()


@app.get("/api/links")
def list_links():
    return {"links": [l.as_dict() for l in store.all()]}


@app.get("/api/links/{slug}/stats")
def stats(slug: str):
    s = store.stats(slug)
    if not s:
        raise HTTPException(404, "link not found")
    return s


@app.delete("/api/links/{slug}")
def deactivate(slug: str):
    if not store.deactivate(slug):
        raise HTTPException(404, "link not found")
    return {"deactivated": slug}


@app.get("/{slug}")
def redirect(slug: str, request: Request,
             referer: str = Header(default=""),
             user_agent: str = Header(default="")):
    target = store.resolve(slug, referrer=referer, user_agent=user_agent,
                           country=request.headers.get("cf-ipcountry", ""))
    if not target:
        raise HTTPException(404, "link not found or inactive")
    # 302 not 301: a permanent redirect would be cached by the browser and we
    # would stop seeing clicks for that visitor forever.
    return RedirectResponse(target, status_code=302)


@app.get("/", response_class=HTMLResponse)
def index():
    rows = "".join(
        f'<tr><td><a href="/{l.slug}">/{l.slug}</a></td>'
        f'<td class="t">{l.target[:52]}</td><td>{l.count}</td>'
        f'<td>{"active" if l.active else "off"}</td></tr>'
        for l in store.all()
    ) or '<tr><td colspan="4">No links yet.</td></tr>'
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>linkforge</title>
<style>
body{{font:15px/1.6 system-ui,sans-serif;max-width:52rem;margin:3rem auto;
padding:0 1.25rem;background:#0f1115;color:#e6e6e6}}
h1{{font-size:1.4rem;letter-spacing:-.02em}}
table{{width:100%;border-collapse:collapse;margin-top:1.5rem;font-size:.9rem}}
th,td{{text-align:left;padding:.6rem .5rem;border-bottom:1px solid #232833}}
th{{color:#8b93a1;font-weight:500;font-size:.78rem;text-transform:uppercase;
letter-spacing:.06em}}
a{{color:#7fb2ff;text-decoration:none}}
.t{{color:#8b93a1;font-family:ui-monospace,monospace;font-size:.82rem}}
.note{{color:#8b93a1;font-size:.85rem;border-left:2px solid #2a3140;
padding-left:.8rem;margin-top:2rem}}
</style></head><body>
<h1>linkforge</h1>
<p>Short links with click analytics.</p>
<table><thead><tr><th>Slug</th><th>Target</th><th>Clicks</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="note">Only http and https targets are accepted — anything else would turn
this into an open redirector.</p>
</body></html>"""
