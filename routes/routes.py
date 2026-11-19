from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from controllers.crud import delete, get_or_404, list_items, save
from database.database import get_db
from models.artista import Artista
from models.genero import Genero
from models.vinilo import Vinilo
from schemas.artista import ArtistaCreate, ArtistaRead
from schemas.genero import GeneroCreate, GeneroRead
from schemas.vinilo import ViniloCreate, ViniloRead


router = APIRouter()


@router.get("/artistas", response_model=list[ArtistaRead])
def list_artistas(db: Session = Depends(get_db)):
    return list_items(db, Artista, Artista.id_artista)


@router.get("/artistas/{item_id}", response_model=ArtistaRead)
def get_artista(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return get_or_404(db, Artista, item_id)


@router.post("/artistas", response_model=ArtistaRead, status_code=201)
def create_artista(data: ArtistaCreate, db: Session = Depends(get_db)):
    return save(db, Artista(**data.model_dump()))


@router.put("/artistas/{item_id}", response_model=ArtistaRead)
def update_artista(data: ArtistaCreate, item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    item = get_or_404(db, Artista, item_id)
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    return save(db, item)


@router.delete("/artistas/{item_id}")
def delete_artista(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return delete(db, get_or_404(db, Artista, item_id))


@router.get("/generos", response_model=list[GeneroRead])
def list_generos(db: Session = Depends(get_db)):
    return list_items(db, Genero, Genero.id_genero)


@router.get("/generos/{item_id}", response_model=GeneroRead)
def get_genero(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return get_or_404(db, Genero, item_id)


@router.post("/generos", response_model=GeneroRead, status_code=201)
def create_genero(data: GeneroCreate, db: Session = Depends(get_db)):
    return save(db, Genero(**data.model_dump()))


@router.put("/generos/{item_id}", response_model=GeneroRead)
def update_genero(data: GeneroCreate, item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    item = get_or_404(db, Genero, item_id)
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    return save(db, item)


@router.delete("/generos/{item_id}")
def delete_genero(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return delete(db, get_or_404(db, Genero, item_id))


@router.get("/vinilos", response_model=list[ViniloRead])
def list_vinilos(db: Session = Depends(get_db)):
    return list_items(db, Vinilo, Vinilo.id_vinilo)


@router.get("/vinilos/{item_id}", response_model=ViniloRead)
def get_vinilo(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return get_or_404(db, Vinilo, item_id)


@router.post("/vinilos", response_model=ViniloRead, status_code=201)
def create_vinilo(data: ViniloCreate, db: Session = Depends(get_db)):
    return save(db, Vinilo(**data.model_dump()))


@router.put("/vinilos/{item_id}", response_model=ViniloRead)
def update_vinilo(data: ViniloCreate, item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    item = get_or_404(db, Vinilo, item_id)
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    return save(db, item)


@router.delete("/vinilos/{item_id}")
def delete_vinilo(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return delete(db, get_or_404(db, Vinilo, item_id))
