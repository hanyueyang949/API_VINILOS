
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.database import Base, engine
from models.artista import Artista
from models.genero import Genero
from models.vinilo import Vinilo


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
