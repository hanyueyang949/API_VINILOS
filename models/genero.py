
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.database import Base


class Genero(Base):
    __tablename__ = "genero"

    id_genero = Column(
        Integer,
        primary_key=True,
        index=True
    )

    tipo = Column(
        String(100),
        unique=True
    )

    vinilos = relationship(
        "Vinilo",
        back_populates="genero",
        passive_deletes="all"
    )
