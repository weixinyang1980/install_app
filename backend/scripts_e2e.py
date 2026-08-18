import json
import sys

import httpx

BASE = "http://127.0.0.1:8765"


def dump(title, data):
    print(f"\n===== {title} =====")
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False, indent=2)
        print(text[:4000])
    else:
        print(str(data)[:4000])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    c = httpx.Client(timeout=120.0)
    r = c.get(f"{BASE}/api/health")
    r.raise_for_status()
    dump("health", r.json())

    r = c.get(f"{BASE}/api/presets")
    r.raise_for_status()
    presets = r.json()["items"]
    print(f"presets: {len(presets)} -> {[p['slug'] for p in presets]}")
    assert len(presets) >= 17

    r = c.post(f"{BASE}/api/parse", json={"query": "我想装 Git"})
    r.raise_for_status()
    dump("parse git", r.json())
    assert r.json()["software"]["slug"] == "git"

    r = c.post(f"{BASE}/api/parse", json={"query": "java jdk"})
    r.raise_for_status()
    dump("parse jdk", r.json())
    assert r.json()["software"]["slug"] == "jdk"

    for slug in ("git", "nodejs", "python", "jdk"):
        r = c.get(f"{BASE}/api/software/{slug}/versions", params={"force": True})
        r.raise_for_status()
        data = r.json()
        vers = [i["version"] for i in data["items"]]
        print(f"versions {slug}: default={data['default']} -> {vers}")
        assert data["items"], slug

    r = c.post(
        f"{BASE}/api/plans/generate",
        json={"slug": "git", "version": "latest", "platform": "windows", "force": True},
    )
    r.raise_for_status()
    plan = r.json()
    dump("git plan keys", {k: plan[k] for k in plan if k != "markdown" and k != "script"})
    assert "Install-ZlmWinget" in plan["script"]
    assert "Git.Git" in plan["script"]
    assert "winget install" not in plan["script"].lower() or "--id" in plan["script"]

    r = c.post(
        f"{BASE}/api/plans/generate",
        json={"slug": "jdk", "version": "17", "platform": "windows", "force": True},
    )
    r.raise_for_status()
    jdk = r.json()
    print("\n===== jdk 17 script excerpt =====")
    print(jdk["script"][-1500:])
    assert "EclipseAdoptium.Temurin" in jdk["script"]
    assert '$feature = "17"' in jdk["script"]
    assert "winget install xxx --version" not in jdk["script"]
    assert "Install-ZlmWinget" in jdk["script"]

    r = c.post(
        f"{BASE}/api/plans/generate",
        json={"slug": "vscode", "version": "stable", "platform": "windows", "force": True},
    )
    r.raise_for_status()
    vs = r.json()
    assert vs["official_url"]
    print("vscode official:", vs["official_url"])

    r = c.post(f"{BASE}/api/parse", json={"query": "我想装 pnpm"})
    r.raise_for_status()
    dump("parse pnpm", r.json())
    pnpm = r.json()["software"]
    r = c.get(f"{BASE}/api/software/{pnpm['slug']}/versions")
    r.raise_for_status()
    dump("pnpm versions", r.json())
    default = r.json()["default"]
    r = c.post(
        f"{BASE}/api/plans/generate",
        json={"slug": pnpm["slug"], "version": default, "platform": "windows", "force": True},
    )
    r.raise_for_status()
    pnpm_plan = r.json()
    print("pnpm source:", pnpm_plan["source"], "has markdown:", bool(pnpm_plan["markdown"]))
    print(pnpm_plan["markdown"][:1500])

    r = c.post(f"{BASE}/api/admin/login", json={"password": "zhuanglema"})
    r.raise_for_status()
    token = r.json()["token"]
    r = c.get(f"{BASE}/api/admin/plans", headers={"X-Admin-Token": token})
    r.raise_for_status()
    print("admin plans:", len(r.json()["items"]))

    r = c.post(f"{BASE}/api/plans/{plan['id']}/feedback", json={"is_valid": True, "comment": "e2e 测试反馈"})
    r.raise_for_status()
    print("feedback ok")
    print("\nALL API TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", type(e), e)
        if hasattr(e, "response") and e.response is not None:
            print(e.response.status_code, e.response.text[:2000])
        sys.exit(1)
