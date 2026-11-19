from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.vinilo import ViniloRead
from schemas.common import NonBlankText


class ArtistaBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class ArtistaCreate(ArtistaBase):
    """Datos admitidos al crear un artista, sin clave primaria."""

    nombre: NonBlankText = Field(max_length=100)


class ArtistaUpdate(ArtistaCreate):
    """Reemplazo completo mediante PUT; los campos omitidos pasan a NULL."""


class ArtistaRead(ArtistaBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id_artista: int = Field(gt=0, strict=True)


class ArtistaDetail(ArtistaRead):
    """Ficha con vinilos asociados, sin referencias anidadas circulares."""

    vinilos: list[ViniloRead]
