#!/usr/bin/env python3
"""Refresh the "Recent Activity" block in README.md from public GitHub data."""

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

USER = os.environ.get("GH_USER", "mkbantu")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
README = Path(__file__).resolve().parents[1] / "README.md"
START = "<!-- ACTIVITY:START -->"
END = "<!-- ACTIVITY:END -->"
MAX_ITEMS = 5
SKIP_REPOS = {"mkbantu"}  # don't let profile-README commits dominate the feed


def api(path: str):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER}-readme-activity",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def clean(text: str) -> str:
    """Make a commit subject safe inside a markdown list item."""
    text = (text or "").splitlines()[0].strip()
    for ch in ("`", "*", "_", "[", "]", "<", ">"):
        text = text.replace(ch, "")
    text = re.sub(r"\s+", " ", text)
    return text[:90] + "…" if len(text) > 90 else text


def pretty_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return ""


def build_block() -> str:
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=20")
    repos = [r for r in repos if not r.get("fork") and not r.get("archived") and r["name"] not in SKIP_REPOS]
    repos.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)

    lines = []
    for repo in repos[:MAX_ITEMS]:
        name, url = repo["name"], repo["html_url"]
        lang = repo.get("language")
        try:
            commits = api(f"/repos/{USER}/{name}/commits?per_page=1")
            commit = commits[0]
            subject = clean(commit["commit"]["message"])
            when = pretty_date(commit["commit"]["author"]["date"])
            detail = f"{subject} · {when}" if when else subject
        except Exception:
            detail = repo.get("description") or "Recently updated"

        meta = " · ".join(part for part in (lang, detail) if part)
        lines.append(f"- **[`{name}`]({url})** — {meta}")

    if not lines:
        return "> Nothing public yet — new work will show up here automatically."

    return "\n".join(lines)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"Markers {START} / {END} not found in README.md")

    pattern = re.compile(f"{re.escape(START)}.*?{re.escape(END)}", re.DOTALL)
    updated = pattern.sub(f"{START}\n{build_block()}\n{END}", text)

    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print("README.md updated")
    else:
        print("README.md already up to date")


if __name__ == "__main__":
    main()
