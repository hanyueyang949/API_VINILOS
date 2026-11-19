from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GeneroCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Optional[str] = Field(default=None, max_length=100)


class GeneroRead(GeneroCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id_genero: int
