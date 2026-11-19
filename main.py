
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.config_variables import CORS_ORIGINS
from database.database import Base, engine
from models.artista import Artista
from models.genero import Genero
from models.vinilo import Vinilo
from routes.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # No devolver el cuerpo recibido ni el contexto interno de los validadores.
    return JSONResponse(status_code=422, content={
        "detail": "Datos de entrada no válidos.",
        "errors": [
            {"loc": error["loc"], "type": error["type"]}
            for error in exc.errors()
        ],
    })


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Inténtalo más tarde."},
    )


# Envolver toda la aplicación para incluir CORS también en respuestas 500.
app = CORSMiddleware(
    app,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
