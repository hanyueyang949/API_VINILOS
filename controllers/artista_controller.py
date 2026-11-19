from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from controllers.crud import delete, get_or_404, list_items, save
from models.artista import Artista
from schemas.artista import ArtistaCreate, ArtistaRead, ArtistaUpdate


def create_artista(db: Session, data: ArtistaCreate) -> ArtistaRead:
    # La restricción UNIQUE de la base evita duplicados incluso con concurrencia.
    return save(db, Artista(**data.model_dump()), ArtistaRead)


def list_artistas(db: Session) -> list[Artista]:
    return list_items(db, Artista, Artista.id_artista)


def get_artista(db: Session, item_id: int) -> Artista:
    statement = (
        select(Artista)
        .where(Artista.id_artista == item_id)
        .options(selectinload(Artista.vinilos))
    )
    artista = db.scalars(statement).one_or_none()
    if artista is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    return artista


def update_artista(db: Session, item_id: int, data: ArtistaUpdate) -> ArtistaRead:
    artista = get_or_404(db, Artista, item_id)
    for field, value in data.model_dump().items():
        setattr(artista, field, value)
    # No se sustituye el artista ni se modifica su ID o sus relaciones.
    return save(db, artista, ArtistaRead)


def delete_artista(db: Session, item_id: int) -> dict:
    artista = get_or_404(db, Artista, item_id)
    # ON DELETE RESTRICT protege también ante escrituras concurrentes;
    # delete traduce el fallo de integridad a 400 y revierte la operación.
    return delete(db, artista)
