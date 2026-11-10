"""Read-only GitHub import through the official REST API (issues, pull requests, comments, commits)."""
import re

import httpx

from ..config import get_settings
from .parsers import ParsedSource, Unit

API = "https://api.github.com"
REPO_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?(?:[#?].*)?$")


class GitHubError(Exception):
    pass


def parse_repo(url: str) -> tuple[str, str]:
    m = REPO_RE.match(url.strip())
    if not m:
        m2 = re.fullmatch(r"([\w.-]+)/([\w.-]+)", url.strip())
        if not m2:
            raise GitHubError("Use a link like https://github.com/owner/repo")
        return m2.group(1), m2.group(2)
    return m.group(1), m.group(2)


def _get(client: httpx.Client, path: str, **params):
    r = client.get(f"{API}{path}", params=params)
    if r.status_code == 404:
        raise GitHubError("Repository not found, or it is private and no access token was given.")
    if r.status_code in (401, 403):
        remaining = r.headers.get("x-ratelimit-remaining")
        if remaining == "0":
            raise GitHubError("GitHub rate limit reached. Add a read-only token or try again later.")
        raise GitHubError("GitHub refused access. Check that the token has read access to this repository.")
    if r.status_code >= 400:
        raise GitHubError(f"GitHub error {r.status_code}: {r.text[:200]}")
    return r.json()


def fetch_repo(url: str, token: str | None = None) -> tuple[str, ParsedSource]:
    owner, repo = parse_repo(url)
    full = f"{owner}/{repo}"
    s = get_settings()
    token = token or s.github_token
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "baton-handover"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    limit = s.github_max_items
    out = ParsedSource()
    with httpx.Client(headers=headers, timeout=20) as client:
        _get(client, f"/repos/{full}")
        issues = _get(client, f"/repos/{full}/issues", state="all", per_page=min(limit, 100),
                      sort="updated", direction="desc")
        for it in issues:
            is_pr = "pull_request" in it
            label = "Pull request" if is_pr else "Issue"
            body = (it.get("body") or "").strip()
            state = it.get("state")
            if it.get("state_reason") == "reopened":
                state = "reopened"
            text = f"{label} #{it['number']} [{state}]: {it['title']}" + (f" — {body}" if body else "")
            out.units.append(Unit(
                kind="github_pr" if is_pr else "github_issue", text=text[:1500],
                author=(it.get("user") or {}).get("login"), occurred_at=(it.get("updated_at") or "")[:10] or None,
                location={"repo": full, "number": it["number"], "url": it.get("html_url")},
            ))
            if it.get("comments"):
                for c in _get(client, f"/repos/{full}/issues/{it['number']}/comments", per_page=30):
                    cbody = (c.get("body") or "").strip()
                    if len(cbody) < 12:
                        continue
                    out.units.append(Unit(
                        kind="github_comment", text=f"Comment on #{it['number']}: {cbody}"[:1500],
                        author=(c.get("user") or {}).get("login"), occurred_at=(c.get("created_at") or "")[:10] or None,
                        location={"repo": full, "number": it["number"], "url": c.get("html_url")},
                    ))
        for c in _get(client, f"/repos/{full}/commits", per_page=min(limit, 100)):
            msg = ((c.get("commit") or {}).get("message") or "").strip()
            if len(msg) < 12:
                continue
            commit = c.get("commit") or {}
            author = (c.get("author") or {}).get("login") or (commit.get("author") or {}).get("name")
            out.units.append(Unit(
                kind="github_commit", text=f"Commit {c['sha'][:7]}: {msg}"[:1500], author=author,
                occurred_at=((commit.get("author") or {}).get("date") or "")[:10] or None,
                location={"repo": full, "sha": c["sha"][:7], "url": c.get("html_url")},
            ))
    return full, out
