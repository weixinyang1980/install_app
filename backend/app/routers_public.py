from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import ai
from .catalog import alias_list, heuristic_parse
from .database import get_db
from .helpers import PS_HELPER
from .models import Feedback, InstallPlan, Software
from .recipes import build_recipe
from .schemas import FeedbackRequest, GenerateRequest, ParseRequest
from .versions import get_versions, match_software

router = APIRouter(prefix="/api")


def software_out(s: Software) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "slug": s.slug,
        "kind": s.kind,
        "official_url": s.official_url,
        "use_official_link": s.use_official_link,
        "platforms": [p for p in s.platforms.split(",") if p],
        "is_preset": s.is_preset,
        "winget_id": s.winget_id,
        "aliases": alias_list(s),
    }


def plan_out(p: InstallPlan, software: Software | None = None) -> dict:
    s = software or p.software
    return {
        "id": p.id,
        "software": software_out(s) if s else None,
        "version": p.version,
        "platform": p.platform,
        "markdown": p.markdown,
        "script": p.script,
        "script_language": p.script_language,
        "official_url": p.official_url,
        "source": p.source,
        "select_count": p.select_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/health")
def health():
    return {"ok": True, "name": "装了吗", "slogan": "今天你装了吗？"}


@router.get("/presets")
def presets(db: Session = Depends(get_db)):
    rows = db.query(Software).filter(Software.is_preset.is_(True)).order_by(Software.id.asc()).all()
    return {"items": [software_out(s) for s in rows]}


@router.post("/parse")
async def parse(req: ParseRequest, db: Session = Depends(get_db)):
    query = req.query.strip()
    matched = match_software(db, query)
    if matched:
        return {"software": software_out(matched), "created": False, "query": query}

    parsed = None
    try:
        parsed = await ai.parse_query(query)
    except Exception as e:
        print(f"[parse] AI 失败，改用本地识别: {type(e).__name__}: {e}")
        parsed = None

    if not parsed or not parsed.get("name"):
        parsed = heuristic_parse(query)

    if parsed and parsed.get("name"):
        slug = (parsed.get("slug") or parsed["name"]).lower().replace(" ", "-")
        existing = db.query(Software).filter(Software.slug == slug).first()
        if existing:
            return {"software": software_out(existing), "created": False, "query": query}
        s = Software(
            name=parsed["name"],
            slug=slug,
            kind=parsed.get("kind") or "other",
            version_source=parsed.get("version_source") or "ai",
            source_key=parsed.get("source_key") or "",
            winget_id=parsed.get("winget_id") or "",
            official_url=parsed.get("official_url") or "",
            use_official_link=bool(parsed.get("use_official_link")),
            platforms=parsed.get("platforms") or "windows,macos,linux",
            aliases=query,
            is_preset=False,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return {"software": software_out(s), "created": True, "query": query}

    raise HTTPException(404, "没听懂要装啥。换个软件名试试，比如 MySQL / Node.js / Git / PHP")


@router.get("/software/{slug}/versions")
async def versions(slug: str, force: bool = False, db: Session = Depends(get_db)):
    s = db.query(Software).filter(Software.slug == slug).first()
    if not s:
        raise HTTPException(404, "没有这个软件")
    items = get_versions(db, s, force=force)
    if (not items or (len(items) == 1 and items[0]["version"] == "latest")) and s.version_source in {"ai", ""}:
        try:
            ai_items = await ai.ai_versions(s.name)
            if ai_items:
                from .versions import save_versions

                items = save_versions(db, s, ai_items)
        except Exception:
            pass
    latest = next((i["version"] for i in items if i.get("is_latest_stable")), items[0]["version"] if items else "latest")
    return {"software": software_out(s), "items": items, "default": latest}


def _ensure_windows_helper(script: str) -> str:
    if not script:
        return script
    if "Install-ZlmWinget" in script or "装了吗 · 安装运行时" in script:
        return script
    if "winget" in script.lower():
        return PS_HELPER.strip() + "\n\n# --- 以下为方案脚本，运行时已注入安全安装函数 ---\n" + script
    return script


def _swap_script(md: str, new_script: str, fence: str) -> str:
    import re as _re

    pat = _re.compile(r"```(?:powershell|ps1|pwsh|bash|sh|zsh|shell)[^\n]*\n.*?```", _re.S)
    block = f"```{fence}\n{new_script.strip()}\n```"
    if pat.search(md):
        return pat.sub(lambda _m: block, md, count=1)
    return md


@router.post("/plans/generate")
async def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    platform = req.platform.lower()
    if platform in {"win32", "win"}:
        platform = "windows"
    if platform in {"darwin", "osx", "mac"}:
        platform = "macos"
    s = db.query(Software).filter(Software.slug == req.slug).first()
    if not s:
        raise HTTPException(404, "没有这个软件")

    existing = (
        db.query(InstallPlan)
        .filter(
            InstallPlan.software_id == s.id,
            InstallPlan.version == req.version,
            InstallPlan.platform == platform,
        )
        .first()
    )
    if existing and not req.force:
        existing.select_count += 1
        db.commit()
        return plan_out(existing, s)

    recipe = build_recipe(s, req.version, platform)
    markdown = ""
    script = ""
    lang = ""
    official = s.official_url if s.use_official_link else ""
    source = "recipe"

    if recipe:
        markdown = recipe["markdown"]
        script = recipe.get("script") or ""
        lang = recipe.get("script_language") or ""
        official = recipe.get("official_url") or official
        source = recipe.get("source") or "recipe"
        # 用 AI 补「执行后建议」，失败就用配方原文
        try:
            refined = await ai.generate_plan_markdown(
                {
                    "name": s.name,
                    "version": req.version,
                    "platform": platform,
                    "winget_id": s.winget_id,
                    "brew": s.brew_cask or s.brew_formula,
                    "official_url": s.official_url,
                    "use_official_link": s.use_official_link,
                    "recipe_script": script or "(官方下载，不需要脚本)",
                }
            )
            if "## 一键安装脚本" in refined or "## 官方安装入口" in refined:
                # 配方脚本更可靠：保留 AI 的说明，但脚本以配方为准
                if script:
                    fence = "powershell" if lang == "powershell" else "bash"
                    markdown = _swap_script(refined, script, fence)
                else:
                    markdown = refined
                source = "recipe+ai"
        except Exception as e:
            print(f"[ai refine skipped] {s.slug}: {e}")
    else:
        source = "ai"
        try:
            markdown = await ai.generate_plan_markdown(
                {
                    "name": s.name,
                    "version": req.version,
                    "platform": platform,
                    "winget_id": s.winget_id,
                    "brew": s.brew_cask or s.brew_formula,
                    "official_url": s.official_url,
                    "use_official_link": s.use_official_link,
                    "recipe_script": "",
                }
            )
        except Exception as e:
            raise HTTPException(502, f"AI 生成失败：{e}")
        script, lang = ai.extract_script(markdown, platform)
        if platform == "windows":
            script = _ensure_windows_helper(script)
            if script and "Install-ZlmWinget" in script and "```powershell" in markdown:
                markdown = _swap_script(markdown, script, "powershell")

    if existing:
        existing.markdown = markdown
        existing.script = script
        existing.script_language = lang
        existing.official_url = official
        existing.source = source
        existing.select_count += 1
        db.commit()
        db.refresh(existing)
        return plan_out(existing, s)

    plan = InstallPlan(
        software_id=s.id,
        version=req.version,
        platform=platform,
        markdown=markdown,
        script=script,
        script_language=lang,
        official_url=official,
        source=source,
        select_count=1,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan_out(plan, s)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    p = db.query(InstallPlan).filter(InstallPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "没有这份方案")
    return plan_out(p)


@router.post("/plans/{plan_id}/feedback")
def feedback(plan_id: int, req: FeedbackRequest, db: Session = Depends(get_db)):
    p = db.query(InstallPlan).filter(InstallPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "没有这份方案")
    fb = Feedback(plan_id=p.id, is_valid=req.is_valid, comment=req.comment or "", status="pending")
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"ok": True, "id": fb.id}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    plans = db.query(InstallPlan).order_by(InstallPlan.select_count.desc()).all()
    items = []
    for p in plans:
        items.append(
            {
                "plan_id": p.id,
                "software": p.software.name if p.software else "",
                "slug": p.software.slug if p.software else "",
                "version": p.version,
                "platform": p.platform,
                "select_count": p.select_count,
            }
        )
    return {"items": items}
