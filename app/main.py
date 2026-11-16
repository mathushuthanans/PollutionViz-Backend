import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import main_routes

app = FastAPI()

# Comma-separated list of allowed browser origins, e.g.
#   CORS_ORIGINS=https://pollutionviz.example.com,http://localhost:5500
# Defaults to "*" (any origin). That is valid only because the API sets no
# cookies and checks no credentials, so allow_credentials stays False.
# Tighten this once JWT auth lands.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_routes.router)
