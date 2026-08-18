from sqlalchemy.orm import Session

from .catalog import PRESET_SOFTWARE
from .models import Software


def seed_presets(db: Session) -> None:
    for item in PRESET_SOFTWARE:
        row = db.query(Software).filter(Software.slug == item["slug"]).first()
        if row:
            for k, v in item.items():
                setattr(row, k, v)
            row.is_preset = True
            continue
        db.add(Software(is_preset=True, **item))
    db.commit()
