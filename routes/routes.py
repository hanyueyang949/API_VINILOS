from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from controllers import libro_controller
from database.database import get_db
from schemas.libro_schema import LibroCreate, LibroUpdate, LibroResponse

router = APIRouter(prefix="/libros", tags=["libros"])


@router.get("/", response_model=list[LibroResponse])
def listar_libros(db: Session = Depends(get_db)):
    return libro_controller.get_libros(db)


@router.get("/{libro_id}", response_model=LibroResponse)
def obtener_libro(libro_id: int, db: Session = Depends(get_db)):
    libro = libro_controller.get_libro(db, libro_id)
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return libro


@router.post("/", response_model=LibroResponse, status_code=201)
def crear_libro(libro: LibroCreate, db: Session = Depends(get_db)):
    return libro_controller.create_libro(db, libro)


@router.put("/{libro_id}", response_model=LibroResponse)
def actualizar_libro(libro_id: int, libro: LibroUpdate, db: Session = Depends(get_db)):
    actualizado = libro_controller.update_libro(db, libro_id, libro)
    if not actualizado:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return actualizado


@router.delete("/{libro_id}")
def eliminar_libro(libro_id: int, db: Session = Depends(get_db)):
    eliminado = libro_controller.delete_libro(db, libro_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return {"message": "Libro eliminado correctamente"}