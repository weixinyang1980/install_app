from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .ai import generate_plan_markdown
from .config import settings
from .database import get_db
from .models import AdminSession, Feedback, InstallPlan, Software
from .recipes import build_recipe
from .routers_public import plan_out, software_out
from .schemas import AdminLoginRequest, PlanUpdateRequest

router = APIRouter(prefix="/api/admin")


def require_admin(x_admin_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not x_admin_token:
        raise HTTPException(401, "未登录")
    row = db.query(AdminSession).filter(AdminSession.token == x_admin_token).first()
    if not row:
        raise HTTPException(401, "登录失效")
    return row


@router.post("/login")
def login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    if req.password != settings.admin_password:
        raise HTTPException(401, "密码不对")
    token = secrets.token_urlsafe(32)
    db.add(AdminSession(token=token))
    db.commit()
    return {"token": token}


@router.get("/plans")
def list_plans(_: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(InstallPlan).order_by(InstallPlan.updated_at.desc()).all()
    return {"items": [plan_out(p) for p in rows]}


@router.put("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    req: PlanUpdateRequest,
    _: AdminSession = Depends(require_admin),
    db: Session = Depends(get_db),
):
    p = db.query(InstallPlan).filter(InstallPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "没有这份方案")
    p.markdown = req.markdown
    if req.script is not None:
        p.script = req.script
    if req.official_url is not None:
        p.official_url = req.official_url
    db.commit()
    return plan_out(p)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.query(InstallPlan).filter(InstallPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "没有这份方案")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/regenerate")
async def regenerate(plan_id: int, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.query(InstallPlan).filter(InstallPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "没有这份方案")
    s = p.software
    recipe = build_recipe(s, p.version, p.platform)
    script = recipe["script"] if recipe else p.script
    md = await generate_plan_markdown(
        {
            "name": s.name,
            "version": p.version,
            "platform": p.platform,
            "winget_id": s.winget_id,
            "brew": s.brew_cask or s.brew_formula,
            "official_url": s.official_url,
            "use_official_link": s.use_official_link,
            "recipe_script": script or "",
        }
    )
    p.markdown = md
    p.source = "admin-ai"
    if recipe:
        p.script = recipe.get("script") or p.script
        p.script_language = recipe.get("script_language") or p.script_language
        p.official_url = recipe.get("official_url") or p.official_url
    db.commit()
    return plan_out(p)


@router.get("/feedbacks")
def list_feedback(_: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    items = []
    for f in rows:
        items.append(
            {
                "id": f.id,
                "plan_id": f.plan_id,
                "software": f.plan.software.name if f.plan and f.plan.software else "",
                "version": f.plan.version if f.plan else "",
                "platform": f.plan.platform if f.plan else "",
                "is_valid": f.is_valid,
                "comment": f.comment,
                "status": f.status,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
        )
    return {"items": items}


@router.patch("/feedbacks/{fid}")
def mark_feedback(fid: int, status: str = "handled", _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    f = db.query(Feedback).filter(Feedback.id == fid).first()
    if not f:
        raise HTTPException(404, "没有这条反馈")
    f.status = status
    db.commit()
    return {"ok": True}


@router.get("/software")
def list_software(_: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Software).order_by(Software.id.asc()).all()
    return {"items": [software_out(s) for s in rows]}
