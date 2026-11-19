import os


# Lista de orígenes exactos separados por comas; sin rutas ni barra final.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
