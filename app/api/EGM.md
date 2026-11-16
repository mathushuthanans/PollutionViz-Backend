# app/api

## Overview
Groups the HTTP layer of the backend. It has no direct source files; all code lives in the `routes` subdirectory.

## Subdirectories & Boundaries
- routes: [./routes/EGM.md](./routes/EGM.md) - FastAPI `APIRouter` exposing the dashboard, ML, and Clarity AI endpoints by delegating to `response_service`.
