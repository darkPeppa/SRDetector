#!/usr/bin/env python3
"""Screenshots of the web UI pages (for the user guide and for visual checks).

    pip install playwright && python -m playwright install chromium
    python tools/ui_screenshots.py --url http://localhost:8080 --out docs/img
    python tools/ui_screenshots.py --url http://localhost:8081 --out docs/img/pink --pages dashboard new

Each page is opened at 1440x900 (light theme), waits for the content and is saved as <name>.png.
Optional highlights (--annotate) draw numbered red frames around the elements the guide refers to.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

# name -> (hash route, css selectors to annotate with numbers, extra JS to run before the shot)
PAGES = {
    "dashboard": ("#/", [".nav", ".topbar .btn.primary", ".grid.g4"], None),
    "new": ("#/new", ["select", "details.sec", ".sticky .card", ".sticky .btn.primary"], None),
    "runs": ("#/runs", ["table.t", ".topbar input"], None),
    "run_overview": ("#/run?path={run}", [".tabs", ".topbar .btn"], None),
    "run_plots": ("#/run?path={run}", [".gallery"], "Alpine.$data(document.querySelector('.layout')).setRunTab('графики')"),
    "run_geometry": ("#/run?path={run}", [".svgbox.big"], "Alpine.$data(document.querySelector('.layout')).setRunTab('геометрия')"),
    "run_3d": ("#/run?path={run}", [], "Alpine.$data(document.querySelector('.layout')).setRunTab('3D')"),
    "run_root": ("#/run?path={run}", [], "Alpine.$data(document.querySelector('.layout')).setRunTab('ROOT')"),
    "studies": ("#/studies", [".grid.g3 .card"], None),
    "optimize": ("#/optimize", [".grid.g3 .card"], None),
    "opt_scan": ("#/opt?path={opt}", [".tabs", "select"], None),
    "opt_dashboard": ("#/opt?path={opt}", [], "Alpine.$data(document.querySelector('.layout')).setOptTab('дашборд')"),
    "jobs": ("#/jobs", [], None),
    "docs": ("#/docs?path=docs/user_guide.md", [], None),
}

ANNOTATE_JS = """(sels) => {
  document.querySelectorAll('.shot-mark').forEach(e => e.remove());
  sels.forEach((s, i) => {
    const el = [...document.querySelectorAll(s)].find(e => e.offsetParent !== null);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const box = document.createElement('div');
    box.className = 'shot-mark';
    Object.assign(box.style, {position: 'fixed', left: r.left - 4 + 'px', top: r.top - 4 + 'px', width: r.width + 8 + 'px',
      height: r.height + 8 + 'px', border: '3px solid #e53935', borderRadius: '8px', zIndex: 99, pointerEvents: 'none'});
    const n = document.createElement('div');
    n.textContent = i + 1;
    Object.assign(n.style, {position: 'absolute', left: '-14px', top: '-14px', width: '26px', height: '26px', borderRadius: '50%',
      background: '#e53935', color: '#fff', font: 'bold 15px sans-serif', display: 'flex', alignItems: 'center', justifyContent: 'center'});
    box.appendChild(n);
    document.body.appendChild(box);
  });
}"""


async def main(a):
    from playwright.async_api import async_playwright
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": a.width, "height": a.height}, color_scheme="light")
        await page.goto(a.url)
        await page.wait_for_timeout(1500)
        runs = await page.evaluate("fetch('/api/runs').then(r => r.json())")
        opts = await page.evaluate("fetch('/api/optimizations').then(r => r.json())")
        run = a.run or next((r["path"] for r in runs if r["status"].startswith("ok") and r.get("mode") == "full"),
                            runs[0]["path"] if runs else "")
        opt = a.opt or next((o["path"] for o in opts["results"] if o["finished"]), "")
        for name in a.pages or PAGES:
            route, marks, js = PAGES[name]
            await page.goto(f"{a.url}/{route.format(run=run, opt=opt)}")
            await page.wait_for_timeout(1800)
            if js:
                await page.evaluate(js)
                await page.wait_for_timeout(a.wait)
            if a.annotate and marks:
                await page.evaluate(ANNOTATE_JS, marks)
            await page.screenshot(path=str(out / f"{name}.png"), full_page=a.full)
            print(f"{name}: {out / f'{name}.png'}")
        await browser.close()
    (out / "pages.json").write_text(json.dumps({"run": run, "opt": opt}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--out", default="docs/img")
    ap.add_argument("--pages", nargs="*", choices=list(PAGES))
    ap.add_argument("--run", help="run folder for the run pages (default: newest successful full run)")
    ap.add_argument("--opt", help="optimisation folder (default: newest finished)")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--wait", type=int, default=3500, help="ms after tab switches (3D, ROOT)")
    ap.add_argument("--full", action="store_true", help="full-page screenshots")
    ap.add_argument("--annotate", action="store_true", help="numbered red frames around key elements")
    asyncio.run(main(ap.parse_args()))
