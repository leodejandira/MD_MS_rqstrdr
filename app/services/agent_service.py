import httpx
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

AGENTS = {
    "rag": "http://host.docker.internal:8000/api/v1/ask",
    "tools": "http://host.docker.internal:8040/api/v1/executar",
    "docs": "http://host.docker.internal:8060/api/v1/processar"
}

async def repassar_para_agente(target_agent: str, payload: dict) -> str:
    """Encaminha o pacote completo para o agente destino e retorna a resposta."""
    target_url = AGENTS.get(target_agent)
    
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(target_url, json=payload)
            response.raise_for_status()
            
            agent_data = response.json()
            return agent_data.get("answer", "Resposta não encontrada.")
            
    except httpx.HTTPError as exc:
        logger.error(f"[NETWORK ERROR] Falha ao contatar {target_agent}: {exc}")
        raise HTTPException(status_code=500, detail=f"O Agente {target_agent} falhou.")