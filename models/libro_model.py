from sqlalchemy import Column, Integer, String, Float

from database.database import Base


class Libro(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False, index=True)
    autor = Column(String, nullable=False)
    anio = Column(Integer, nullable=True)
    genero = Column(String, nullable=True)
    precio = Column(Float, nullable=True)