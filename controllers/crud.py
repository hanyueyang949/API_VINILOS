from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


def get_or_404(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    return item


def list_items(db: Session, model, primary_key):
    return db.scalars(select(model).order_by(primary_key)).all()


def save(db: Session, item):
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se pudo guardar: hay datos duplicados o referencias no válidas.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No se pudo guardar el recurso. Inténtalo más tarde."
        ) from None
    return item


def delete(db: Session, item):
    try:
        db.delete(item)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el recurso porque tiene vinilos asociados.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No se pudo eliminar el recurso. Inténtalo más tarde."
        ) from None
    return {"detail": "Recurso eliminado correctamente."}
