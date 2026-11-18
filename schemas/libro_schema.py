from typing import Optional

from pydantic import BaseModel


class LibroBase(BaseModel):
    titulo: str
    autor: str
    anio: Optional[int] = None
    genero: Optional[str] = None
    precio: Optional[float] = None


class LibroCreate(LibroBase):
    pass


class LibroUpdate(BaseModel):
    titulo: Optional[str] = None
    autor: Optional[str] = None
    anio: Optional[int] = None
    genero: Optional[str] = None
    precio: Optional[float] = None


class LibroResponse(LibroBase):
    id: int

    model_config = {"from_attributes": True}