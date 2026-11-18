
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database.database import Base


class Artista(Base):
    __tablename__ = "artista"

    id_artista = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nombre = Column(
        String(100),
        unique=True
    )

    descripcion = Column(String(500))

    vinilos = relationship(
        "Vinilo",
        back_populates="artista",
        passive_deletes="all"
    )
