from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from schemas.common import NonBlankText


class GeneroBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Optional[str] = Field(default=None, max_length=100)


class GeneroCreate(GeneroBase):
    """Datos admitidos al crear un género, sin clave primaria."""

    tipo: NonBlankText = Field(max_length=100)


class GeneroUpdate(GeneroCreate):
    """Reemplazo completo mediante PUT; los campos omitidos pasan a NULL."""


class GeneroRead(GeneroBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id_genero: int = Field(gt=0, strict=True)
