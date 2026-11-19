from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ArtistaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class ArtistaRead(ArtistaCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id_artista: int
