"""
SoloLedger FastAPI application entry point.

Run from the backend/ folder with:  uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from routers.clients import router as clients_router
from routers.expenses import router as expenses_router
from routers.invoices import router as invoices_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and seed sample data once when the server starts.
    database.init_db()
    yield


app = FastAPI(
    title="SoloLedger API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients_router)
app.include_router(invoices_router)
app.include_router(expenses_router)


@app.get("/")
def root():
    return {"message": "SoloLedger API is running", "docs": "/docs"}
