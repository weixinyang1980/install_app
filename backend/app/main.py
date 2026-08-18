from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import ROOT, settings
from .database import Base, SessionLocal, engine
from .routers_admin import router as admin_router
from .routers_public import router as public_router
from .seed import seed_presets

(ROOT / "data").mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_presets(db)

app = FastAPI(title="装了吗", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public_router)
app.include_router(admin_router)

admin_dist = ROOT.parent / "admin" / "dist"
if admin_dist.is_dir():
    app.mount("/admin", StaticFiles(directory=str(admin_dist), html=True), name="admin")


@app.get("/")
def root():
    return {
        "name": "装了吗",
        "slogan": "今天你装了吗？",
        "docs": "/docs",
        "health": "/api/health",
    }


def run():
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
