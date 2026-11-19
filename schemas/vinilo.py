from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ViniloCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    titulo: Optional[str] = Field(default=None, max_length=150)
    anio: Optional[int] = Field(default=None, alias="año")
    precio: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    descripcion: Optional[str] = None
    artista_id: int = Field(gt=0)
    genero_id: int = Field(gt=0)


class ViniloRead(ViniloCreate):
    model_config = ConfigDict(
        from_attributes=True, extra="forbid", populate_by_name=True
    )

    id_vinilo: int
