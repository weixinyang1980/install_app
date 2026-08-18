from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from .catalog import alias_list
from .config import settings
from .models import Software, VersionCache, utcnow

UA = {"User-Agent": "ZhuangLeMa/1.0 (install helper; +https://localhost)"}


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0, headers=UA, follow_redirects=True)


def cache_fresh(db: Session, software: Software) -> bool:
    row = (
        db.query(VersionCache)
        .filter(VersionCache.software_id == software.id)
        .order_by(VersionCache.fetched_at.desc())
        .first()
    )
    if not row:
        return False
    fetched = row.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched < timedelta(hours=settings.version_cache_hours)


def list_cached(db: Session, software: Software) -> list[dict]:
    rows = (
        db.query(VersionCache)
        .filter(VersionCache.software_id == software.id)
        .order_by(VersionCache.is_latest_stable.desc(), VersionCache.id.asc())
        .all()
    )
    return [
        {"version": r.version, "channel": r.channel, "is_latest_stable": r.is_latest_stable}
        for r in rows
    ]


def save_versions(db: Session, software: Software, versions: list[dict]) -> list[dict]:
    db.query(VersionCache).filter(VersionCache.software_id == software.id).delete()
    db.flush()
    if not versions:
        db.commit()
        return []
    unique: list[dict] = []
    seen: set[str] = set()
    for item in versions:
        ver = str(item.get("version") or "").strip()
        if not ver or ver in seen:
            continue
        seen.add(ver)
        unique.append({**item, "version": ver})
    if not unique:
        db.commit()
        return []
    unique[0]["is_latest_stable"] = True
    now = utcnow()
    for item in unique:
        db.add(
            VersionCache(
                software_id=software.id,
                version=item["version"],
                channel=item.get("channel", "stable"),
                is_latest_stable=bool(item.get("is_latest_stable")),
                fetched_at=now,
            )
        )
    db.commit()
    return list_cached(db, software)


def fetch_endoflife(product: str) -> list[dict]:
    with _client() as c:
        r = c.get(f"https://endoflife.date/api/{product}.json")
        r.raise_for_status()
        data = r.json()
    out = []
    for item in data[:12]:
        latest = str(item.get("latest") or item.get("cycle") or "")
        if not latest:
            continue
        channel = "lts" if item.get("lts") else "stable"
        out.append({"version": latest, "channel": channel, "is_latest_stable": False})
    return out


def fetch_nodejs() -> list[dict]:
    with _client() as c:
        r = c.get("https://nodejs.org/dist/index.json")
        r.raise_for_status()
        data = r.json()
    lts_rows = []
    current = None
    seen_majors = set()
    for item in data:
        ver = item["version"].lstrip("v")
        major = ver.split(".")[0]
        lts = item.get("lts")
        if lts:
            if major in seen_majors:
                continue
            seen_majors.add(major)
            lts_rows.append({"version": ver, "channel": "lts", "is_latest_stable": False})
        elif current is None:
            current = {"version": ver, "channel": "current", "is_latest_stable": False}
        if len(lts_rows) >= 7:
            break
    out = lts_rows[:]
    if current:
        out.append(current)
    return out[:8]


def fetch_python() -> list[dict]:
    rows = fetch_endoflife("python")
    # keep 3.x only
    return [x for x in rows if x["version"].startswith("3.")][:8]


def fetch_go() -> list[dict]:
    with _client() as c:
        r = c.get("https://go.dev/dl/?mode=json")
        r.raise_for_status()
        data = r.json()
    out = []
    for item in data[:8]:
        ver = item.get("version", "").removeprefix("go")
        if ver:
            out.append({"version": ver, "channel": "stable", "is_latest_stable": False})
    return out


def fetch_adoptium() -> list[dict]:
    with _client() as c:
        r = c.get(
            "https://api.adoptium.net/v3/info/release_versions",
            params={"release_type": "ga", "page_size": 40, "project": "jdk", "sort_order": "DESC"},
        )
        r.raise_for_status()
        versions = r.json().get("versions", [])
    lts_features = {"8", "11", "17", "21", "25"}
    lts_rows = []
    other = []
    seen = set()
    for v in versions:
        feature = str(v.get("major") or v.get("semver", "").split(".")[0])
        semver = v.get("semver") or v.get("openjdk_version") or feature
        if feature in seen:
            continue
        seen.add(feature)
        row = {
            "version": str(semver).split("+")[0],
            "channel": "lts" if feature in lts_features else "stable",
            "is_latest_stable": False,
        }
        if feature in lts_features:
            lts_rows.append(row)
        else:
            other.append(row)
    return (lts_rows + other)[:8]


def fetch_github_releases(repo: str) -> list[dict]:
    with _client() as c:
        r = c.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 12})
        if r.status_code == 403:
            return []
        r.raise_for_status()
        data = r.json()
    out = []
    for item in data:
        if item.get("draft") or item.get("prerelease"):
            continue
        tag = (item.get("tag_name") or "").lstrip("vV")
        tag = re.sub(r"^git-for-windows[-.]?", "", tag, flags=re.I)
        m = re.search(r"\d+\.\d+(\.\d+)*", tag)
        if not m:
            continue
        out.append({"version": m.group(0), "channel": "stable", "is_latest_stable": False})
        if len(out) >= 8:
            break
    return out


def fetch_npm(pkg: str) -> list[dict]:
    with _client() as c:
        r = c.get(f"https://registry.npmjs.org/{pkg}")
        r.raise_for_status()
        data = r.json()
    tags = data.get("dist-tags", {})
    latest = tags.get("latest")
    versions = list(data.get("versions", {}).keys())
    versions.sort(key=lambda s: [int(x) if x.isdigit() else 0 for x in re.split(r"\D+", s)], reverse=True)
    out = []
    if latest:
        out.append({"version": latest, "channel": "latest", "is_latest_stable": True})
    for v in versions:
        if v == latest:
            continue
        if re.search(r"-(alpha|beta|rc|next|canary|dev)", v, re.I):
            continue
        out.append({"version": v, "channel": "stable", "is_latest_stable": False})
        if len(out) >= 8:
            break
    return out


def fetch_pypi(pkg: str) -> list[dict]:
    with _client() as c:
        r = c.get(f"https://pypi.org/pypi/{pkg}/json")
        r.raise_for_status()
        data = r.json()
    latest = data.get("info", {}).get("version")
    vers = list(data.get("releases", {}).keys())
    vers.sort(reverse=True)
    out = []
    if latest:
        out.append({"version": latest, "channel": "latest", "is_latest_stable": True})
    for v in vers:
        if v == latest:
            continue
        if re.search(r"a|b|rc|dev", v, re.I):
            continue
        out.append({"version": v, "channel": "stable", "is_latest_stable": False})
        if len(out) >= 8:
            break
    return out


def fetch_maven(coord: str) -> list[dict]:
    # coord: group:artifact
    if ":" not in coord:
        return []
    group, artifact = coord.split(":", 1)
    with _client() as c:
        r = c.get(
            "https://search.maven.org/solrsearch/select",
            params={"q": f"g:{group} AND a:{artifact}", "rows": 8, "wt": "json", "core": "gav"},
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
    out = []
    for d in docs:
        v = d.get("v")
        if v:
            out.append({"version": v, "channel": "stable", "is_latest_stable": False})
    return out


STATIC_VERSIONS = {
    "docker": [
        {"version": "latest", "channel": "stable", "is_latest_stable": True},
    ],
    "rust": [
        {"version": "stable", "channel": "stable", "is_latest_stable": True},
        {"version": "beta", "channel": "beta", "is_latest_stable": False},
        {"version": "nightly", "channel": "nightly", "is_latest_stable": False},
    ],
    "vscode": [
        {"version": "stable", "channel": "stable", "is_latest_stable": True},
        {"version": "insiders", "channel": "insiders", "is_latest_stable": False},
    ],
    "idea": [
        {"version": "latest", "channel": "stable", "is_latest_stable": True},
    ],
    "homebrew": [
        {"version": "latest", "channel": "stable", "is_latest_stable": True},
    ],
}


def fetch_for_software(software: Software) -> list[dict]:
    src = software.version_source
    key = software.source_key or software.slug
    try:
        if src == "endoflife":
            return fetch_endoflife(key)
        if src == "nodejs":
            return fetch_nodejs()
        if src == "python":
            return fetch_python()
        if src == "go":
            return fetch_go()
        if src == "adoptium":
            return fetch_adoptium()
        if src == "github":
            return fetch_github_releases(key)
        if src == "npm":
            return fetch_npm(key)
        if src == "pypi":
            return fetch_pypi(key)
        if src == "maven":
            return fetch_maven(key)
        if src == "static":
            return STATIC_VERSIONS.get(key, [{"version": "latest", "channel": "stable", "is_latest_stable": True}])
    except Exception:
        return []
    return []


def get_versions(db: Session, software: Software, force: bool = False) -> list[dict]:
    if not force and cache_fresh(db, software):
        cached = list_cached(db, software)
        if cached:
            return cached
    fetched = fetch_for_software(software)
    if fetched:
        try:
            return save_versions(db, software, fetched)
        except Exception:
            db.rollback()
            cached = list_cached(db, software)
            if cached:
                return cached
    cached = list_cached(db, software)
    if cached:
        return cached
    fallback = [{"version": "latest", "channel": "stable", "is_latest_stable": True}]
    try:
        return save_versions(db, software, fallback)
    except Exception:
        db.rollback()
        return fallback


def match_software(db: Session, query: str) -> Software | None:
    q = query.strip().lower()
    q = re.sub(r"我想装|帮我装|请帮我安装|安装|download|install", "", q).strip()
    q = re.sub(r"[\s_-]+", "", q)
    if not q:
        return None
    rows = db.query(Software).all()
    for row in rows:
        aliases = alias_list(row)
        compact_name = re.sub(r"[\s_-]+", "", row.name.lower())
        compact_slug = re.sub(r"[\s_-]+", "", row.slug.lower())
        if q in aliases or q == compact_slug or q == compact_name:
            return row
    if len(q) >= 3:
        for row in rows:
            compact_name = re.sub(r"[\s_-]+", "", row.name.lower())
            if q in compact_name or compact_name in q:
                return row
            for a in alias_list(row):
                a2 = re.sub(r"[\s_-]+", "", a)
                if len(a2) >= 3 and (a2 in q or q in a2):
                    return row
    return None
