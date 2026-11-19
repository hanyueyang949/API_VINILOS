from typing import Optional

from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from controllers.crud import delete, save
from models.vinilo import Vinilo
from schemas.vinilo import ViniloCreate, ViniloRead, ViniloUpdate


def create_vinilo(db: Session, data: ViniloCreate) -> ViniloRead:
    # Las FK obligatorias y UNIQUE(titulo, artista_id) se verifican en la base,
    # también ante altas concurrentes. save revierte los fallos y devuelve 400.
    # model_dump usa "anio", el atributo ORM de la columna SQL "año".
    return save(db, Vinilo(**data.model_dump()), ViniloRead)


def list_vinilos(db: Session, genero_id: Optional[int] = None) -> list[Vinilo]:
    statement = select(Vinilo).order_by(Vinilo.id_vinilo)
    if genero_id is not None:
        statement = statement.where(Vinilo.genero_id == genero_id)
    return db.scalars(statement).all()


def get_vinilo(db: Session, item_id: int) -> Vinilo:
    statement = (
        select(Vinilo)
        .where(Vinilo.id_vinilo == item_id)
        .options(joinedload(Vinilo.artista), joinedload(Vinilo.genero))
    )
    vinilo = db.scalars(statement).one_or_none()
    if vinilo is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    return vinilo


def update_vinilo(db: Session, item_id: int, data: ViniloUpdate) -> ViniloRead:
    vinilo = get_vinilo(db, item_id)
    for field, value in data.model_dump().items():
        setattr(vinilo, field, value)
    # Datos y FK se guardan juntos: cualquier conflicto revierte todos los cambios.
    return save(db, vinilo, ViniloRead)


def delete_vinilo(db: Session, item_id: int) -> dict:
    vinilo = get_vinilo(db, item_id)
    # Se elimina únicamente el vinilo, sin borrar su artista ni su género.
    return delete(db, vinilo)
