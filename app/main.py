from fastapi import FastAPI
import logging
from api.routes import router as orchestrator_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="MindDesk - Orquestrador de Agentes")

# Inclui as rotas separadas
app.include_router(orchestrator_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)