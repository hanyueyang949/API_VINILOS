from sqlalchemy.orm import Session

from controllers.crud import delete, get_or_404, list_items, save
from models.genero import Genero
from schemas.genero import GeneroCreate, GeneroRead, GeneroUpdate


def create_genero(db: Session, data: GeneroCreate) -> GeneroRead:
    # UNIQUE en la base protege frente a duplicados, incluso con concurrencia.
    return save(db, Genero(**data.model_dump()), GeneroRead)


def list_generos(db: Session) -> list[Genero]:
    return list_items(db, Genero, Genero.id_genero)


def get_genero(db: Session, item_id: int) -> Genero:
    return get_or_404(db, Genero, item_id)


def update_genero(db: Session, item_id: int, data: GeneroUpdate) -> GeneroRead:
    genero = get_genero(db, item_id)
    genero.tipo = data.tipo
    # Conservar el registro y su ID mantiene las asociaciones de los vinilos.
    return save(db, genero, GeneroRead)


def delete_genero(db: Session, item_id: int) -> dict:
    genero = get_genero(db, item_id)
    # ON DELETE RESTRICT bloquea géneros vinculados; delete hace rollback
    # y devuelve el mensaje de borrado protegido acordado (400).
    return delete(db, genero)
