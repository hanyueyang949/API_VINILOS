
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DECIMAL,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from database.database import Base


class Vinilo(Base):
    __tablename__ = "vinilo"

    id_vinilo = Column(
        Integer,
        primary_key=True,
        index=True
    )

    titulo = Column(String(150))

    anio = Column("año", Integer)

    precio = Column(DECIMAL(10, 2))

    descripcion = Column(Text)

    artista_id = Column(
        Integer,
        ForeignKey(
            "artista.id_artista",
            ondelete="RESTRICT"
        ),
        nullable=False
    )

    genero_id = Column(
        Integer,
        ForeignKey(
            "genero.id_genero",
            ondelete="RESTRICT"
        ),
        nullable=False
    )

    artista = relationship(
        "Artista",
        back_populates="vinilos"
    )

    genero = relationship(
        "Genero",
        back_populates="vinilos"
    )

    __table_args__ = (
        UniqueConstraint(
            "titulo",
            "artista_id",
            name="uq_vinilo_titulo_artista"
        ),
    )
