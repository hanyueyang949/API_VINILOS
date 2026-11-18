from sqlalchemy.orm import Session

from models.libro_model import Libro
from schemas.libro_schema import LibroCreate, LibroUpdate


def get_libros(db: Session):
    return db.query(Libro).all()


def get_libro(db: Session, libro_id: int):
    return db.query(Libro).filter(Libro.id == libro_id).first()


def create_libro(db: Session, libro: LibroCreate):
    db_libro = Libro(**libro.model_dump())
    db.add(db_libro)
    db.commit()
    db.refresh(db_libro)
    return db_libro


def update_libro(db: Session, libro_id: int, libro: LibroUpdate):
    db_libro = get_libro(db, libro_id)
    if not db_libro:
        return None
    for key, value in libro.model_dump(exclude_unset=True).items():
        setattr(db_libro, key, value)
    db.commit()
    db.refresh(db_libro)
    return db_libro


def delete_libro(db: Session, libro_id: int):
    db_libro = get_libro(db, libro_id)
    if not db_libro:
        return None
    db.delete(db_libro)
    db.commit()
    return db_libro