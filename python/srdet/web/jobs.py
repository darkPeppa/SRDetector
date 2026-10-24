"""Background job queue for the web UI. Every job is a `srdet ...` CLI call in a subprocess;
jobs run one after another (each simulation already uses all cores). The registry and logs
live in runs/web_jobs/ so they survive a restart of the server."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from ..paths import repo_root, runs_dir

RESULT_PATTERNS = [
    re.compile(r"optimize done: (?P<p>\S+)/report\.md"),
    re.compile(r"study \S+ done: (?P<p>\S+)"),
    re.compile(r"pictures in (?P<p>\S+)"),
    re.compile(r"\[srdet\] run \S+: (?P<p>\S+)"),
]


class JobManager:
    def __init__(self, base: Path | None = None):
        self.dir = base or runs_dir() / "web_jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.registry = self.dir / "jobs.json"
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}
        self.queue: list[str] = []
        self.procs: dict[str, subprocess.Popen] = {}
        self.cond = threading.Condition(self.lock)
        if self.registry.exists():
            self.jobs = json.loads(self.registry.read_text())
            for j in self.jobs.values():  # anything unfinished died with the previous server
                if j["status"] in ("queued", "running"):
                    j["status"] = "interrupted"
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------------- public API
    def submit(self, kind: str, args: list[str], title: str, meta: dict | None = None) -> dict:
        jid = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        job = {"id": jid, "kind": kind, "title": title, "args": args, "status": "queued",
               "created": dt.datetime.now().isoformat(timespec="seconds"), "started": None, "finished": None,
               "returncode": None, "result": None, "log": str(self.dir / f"{jid}.log"), "meta": meta or {}}
        with self.cond:
            self.jobs[jid] = job
            self.queue.append(jid)
            self._save()
            self.cond.notify()
        return job

    def get(self, jid: str, tail: int = 200) -> dict | None:
        job = self.jobs.get(jid)
        if not job:
            return None
        out = dict(job)
        log = Path(job["log"])
        out["log_tail"] = "\n".join(log.read_text(errors="replace").splitlines()[-tail:]) if log.exists() else ""
        out["result"] = job.get("result") or self._result(out["log_tail"])
        return out

    def list(self) -> list[dict]:
        return sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True)

    def cancel(self, jid: str) -> bool:
        with self.cond:
            job = self.jobs.get(jid)
            if not job:
                return False
            if job["status"] == "queued":
                self.queue.remove(jid)
                job["status"] = "cancelled"
                self._save()
                return True
            proc = self.procs.get(jid)
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)  # srdet-sim runs in the same process group
            return True
        return False

    # ---------------- worker
    def _worker(self):
        while True:
            with self.cond:
                while not self.queue:
                    self.cond.wait()
                jid = self.queue.pop(0)
                job = self.jobs[jid]
                job["status"] = "running"
                job["started"] = dt.datetime.now().isoformat(timespec="seconds")
                self._save()
            env = dict(os.environ, PYTHONUNBUFFERED="1")
            with open(job["log"], "w") as log:
                log.write(f"$ srdet {' '.join(job['args'])}\n")
                log.flush()
                proc = subprocess.Popen([sys.executable, "-m", "srdet.cli", *job["args"]], cwd=repo_root(),
                                        stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                with self.lock:
                    self.procs[jid] = proc
                rc = proc.wait()
            with self.cond:
                self.procs.pop(jid, None)
                job["returncode"] = rc
                job["finished"] = dt.datetime.now().isoformat(timespec="seconds")
                if job["status"] != "cancelled":
                    job["status"] = "done" if rc == 0 else ("cancelled" if rc < 0 else "failed")
                text = Path(job["log"]).read_text(errors="replace")
                job["result"] = self._result(text)
                self._after(job)
                self._save()

    def _after(self, job: dict):
        """Link geometry pictures back to the run they were made for."""
        src, res = job["meta"].get("source_run"), job.get("result")
        if job["kind"] == "vis" and src and res and job["status"] == "done":
            f = repo_root() / src / "vis.json"
            links = json.loads(f.read_text()) if f.exists() else []
            links.append(res)
            f.write_text(json.dumps(links))

    @staticmethod
    def _result(text: str) -> str | None:
        root = str(repo_root())
        for pat in RESULT_PATTERNS:
            hits = pat.findall(text)
            if hits:
                p = hits[-1]
                p = p.replace("/work/", "") if p.startswith("/work/") else p
                return os.path.relpath(p, root) if p.startswith(root) else p
        return None

    def _save(self):
        self.registry.write_text(json.dumps(self.jobs, indent=1))
