"""Dependency-free local investigation UI."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Type
from urllib.parse import unquote, urlparse

from .investigate import investigate
from .store import SQLiteStore


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Agent Flight Recorder</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#141b2d;--muted:#94a3b8;--line:#26324c;--ok:#34d399;--bad:#fb7185;--accent:#60a5fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#e5e7eb;font:15px system-ui,sans-serif}
header{padding:24px 28px;border-bottom:1px solid var(--line)}h1{margin:0;font-size:22px}header p{margin:5px 0 0;color:var(--muted)}
main{display:grid;grid-template-columns:330px 1fr;min-height:calc(100vh - 92px)}aside{border-right:1px solid var(--line);padding:18px}section{padding:26px;max-width:1000px}
input{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;background:#0f172a;color:white;margin-bottom:14px}
.run,.step{display:block;width:100%;text-align:left;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:12px;margin:8px 0;cursor:pointer}.run:hover{border-color:var(--accent)}
.meta{color:var(--muted);font-size:13px}.failed{color:var(--bad)}.ok{color:var(--ok)}.step{cursor:default}.badge{float:right;font-size:12px}pre{white-space:pre-wrap;background:#080d19;border:1px solid var(--line);padding:14px;border-radius:8px;overflow:auto}.empty{color:var(--muted)}
@media(max-width:700px){main{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--line)}}
</style></head><body><header><h1>Agent Flight Recorder</h1><p>Local evidence, replay and failure investigation</p></header>
<main><aside><input id="search" placeholder="Search runs…"><div id="runs"></div></aside><section id="detail"><p class="empty">Select a recorded run.</p></section></main>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let all=[];
async function load(){all=await(await fetch('/api/runs')).json();drawRuns();if(all[0])show(all[0].id)}
function drawRuns(){let q=document.querySelector('#search').value.toLowerCase();document.querySelector('#runs').innerHTML=all.filter(r=>(r.id+' '+r.name).toLowerCase().includes(q)).map(r=>`<button class="run" onclick="show('${esc(r.id)}')"><span class="badge ${r.status}">${esc(r.status)}</span><b>${esc(r.name)}</b><div class="meta">${esc(r.id)}</div></button>`).join('')||'<p class="empty">No matching runs.</p>'}
async function show(id){let [r,i]=await Promise.all([fetch('/api/runs/'+encodeURIComponent(id)).then(x=>x.json()),fetch('/api/investigate/'+encodeURIComponent(id)).then(x=>x.json())]);let suspect=i.suspect?`<h3>Investigation</h3><p>First suspect: <b>#${i.suspect.sequence} ${esc(i.suspect.name)}</b></p><pre>${esc((i.diff||[]).join('\n'))}</pre>`:'';let steps=r.steps.map(s=>`<div class="step"><span class="badge ${s.status}">${esc(s.status)}</span><b>#${s.sequence} ${esc(s.name)}</b><div class="meta">${esc(s.kind)}</div>${s.error?`<pre>${esc(s.error)}</pre>`:''}</div>`).join('');document.querySelector('#detail').innerHTML=`<h2>${esc(r.name)}</h2><p class="meta">${esc(r.id)} · ${esc(r.status)}</p>${suspect}<h3>Timeline</h3>${steps}`}
document.querySelector('#search').addEventListener('input',drawRuns);load();
</script></body></html>"""


def api_response(store: SQLiteStore, path: str) -> Any:
    """Resolve an API path independently of the HTTP transport."""
    if path == "/api/runs":
        return 200, store.list_runs(100)
    match = re.fullmatch(r"/api/(runs|investigate)/([^/]+)", path)
    if match:
        run = store.get_run(match.group(2))
        if run is None:
            return 404, {"error": "run not found"}
        return 200, run if match.group(1) == "runs" else investigate(run)
    return 404, {"error": "not found"}


def handler_for(store: SQLiteStore) -> Type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: Any, status: int = 200) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            path = unquote(urlparse(self.path).path)
            if path == "/":
                encoded = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            if path.startswith("/api/"):
                status, payload = api_response(store, path)
                self._json(payload, status)
                return
            self._json({"error": "not found"}, 404)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def serve(store: SQLiteStore, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), handler_for(store))
    print("Flight Recorder UI: http://%s:%d" % (host, server.server_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

