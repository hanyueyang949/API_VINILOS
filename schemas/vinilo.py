from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from schemas.common import NonBlankText


class ViniloBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    titulo: Optional[str] = Field(default=None, max_length=150)
    anio: Optional[int] = Field(default=None, alias="año", strict=True)
    precio: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    descripcion: Optional[str] = None
    artista_id: int = Field(gt=0, strict=True)
    genero_id: int = Field(gt=0, strict=True)


class ViniloCreate(ViniloBase):
    """Exige artista y género; su existencia se comprueba en la base de datos."""

    titulo: NonBlankText = Field(max_length=150)
    precio: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class ViniloUpdate(ViniloCreate):
    """PUT completo, con artista y género obligatorios y modificables."""


class ViniloRead(ViniloBase):
    model_config = ConfigDict(
        from_attributes=True, extra="forbid", populate_by_name=True
    )

    id_vinilo: int = Field(gt=0, strict=True)


class ArtistaSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_artista: int
    nombre: Optional[str]


class GeneroSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_genero: int
    tipo: Optional[str]


class ViniloDetail(ViniloRead):
    artista: ArtistaSummary
    genero: GeneroSummary


class ViniloFilter(BaseModel):
    genero_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("genero_id", mode="before")
    @classmethod
    def validate_genero_id(cls, value):
        # El query llega como texto: impedir que "1.0" se convierta a entero.
        if isinstance(value, str) and not (value.isascii() and value.isdecimal()):
            raise ValueError("genero_id debe ser un entero positivo.")
        return value
