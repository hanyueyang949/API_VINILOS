from fastapi import FastAPI

from config.config_variables import APP_NAME, DEBUG
from database.database import Base, engine
from routes.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_NAME, debug=DEBUG)

app.include_router(router)


@app.get("/")
def root():
    return {"message": f"Bienvenido a {APP_NAME}"}