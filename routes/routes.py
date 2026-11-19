from typing_extensions import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from controllers import artista_controller, genero_controller, vinilo_controller
from database.database import get_db
from schemas.artista import ArtistaCreate, ArtistaDetail, ArtistaRead, ArtistaUpdate
from schemas.genero import GeneroCreate, GeneroRead, GeneroUpdate
from schemas.vinilo import ViniloCreate, ViniloDetail, ViniloFilter, ViniloRead, ViniloUpdate


router = APIRouter()


@router.get("/artistas", response_model=list[ArtistaRead])
def list_artistas(db: Session = Depends(get_db)):
    return artista_controller.list_artistas(db)


@router.get("/artistas/{item_id}", response_model=ArtistaDetail)
def get_artista(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return artista_controller.get_artista(db, item_id)


@router.post("/artistas", response_model=ArtistaRead, status_code=201)
def create_artista(data: ArtistaCreate, db: Session = Depends(get_db)):
    return artista_controller.create_artista(db, data)


@router.put("/artistas/{item_id}", response_model=ArtistaRead)
def update_artista(
    data: ArtistaUpdate,
    item_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return artista_controller.update_artista(db, item_id, data)


@router.delete("/artistas/{item_id}")
def delete_artista(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return artista_controller.delete_artista(db, item_id)


@router.get("/generos", response_model=list[GeneroRead])
def list_generos(db: Session = Depends(get_db)):
    return genero_controller.list_generos(db)


@router.get("/generos/{item_id}", response_model=GeneroRead)
def get_genero(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return genero_controller.get_genero(db, item_id)


@router.post("/generos", response_model=GeneroRead, status_code=201)
def create_genero(data: GeneroCreate, db: Session = Depends(get_db)):
    return genero_controller.create_genero(db, data)


@router.put("/generos/{item_id}", response_model=GeneroRead)
def update_genero(
    data: GeneroUpdate,
    item_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return genero_controller.update_genero(db, item_id, data)


@router.delete("/generos/{item_id}")
def delete_genero(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return genero_controller.delete_genero(db, item_id)


@router.get("/vinilos", response_model=list[ViniloRead])
def list_vinilos(
    filters: Annotated[ViniloFilter, Query()],
    db: Session = Depends(get_db),
):
    return vinilo_controller.list_vinilos(db, filters.genero_id)


@router.get("/vinilos/{item_id}", response_model=ViniloDetail)
def get_vinilo(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return vinilo_controller.get_vinilo(db, item_id)


@router.post("/vinilos", response_model=ViniloRead, status_code=201)
def create_vinilo(data: ViniloCreate, db: Session = Depends(get_db)):
    return vinilo_controller.create_vinilo(db, data)


@router.put("/vinilos/{item_id}", response_model=ViniloRead)
def update_vinilo(
    data: ViniloUpdate,
    item_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    return vinilo_controller.update_vinilo(db, item_id, data)


@router.delete("/vinilos/{item_id}")
def delete_vinilo(item_id: int = Path(gt=0), db: Session = Depends(get_db)):
    return vinilo_controller.delete_vinilo(db, item_id)
