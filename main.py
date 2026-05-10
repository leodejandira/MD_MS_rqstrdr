from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import logging

app = FastAPI(title="MindDesk - Orquestrador de Agentes")
logging.basicConfig(level=logging.INFO)

AGENTS = {
    "rag": "http://host.docker.internal:8000/api/v1/ask",
    "tools": "http://host.docker.internal:8040/api/v1/executar"
}

class OrchestratorRequest(BaseModel):
    query: str
    tenant_id: int
    user_id: str
    role: str  
    current_agent: str = "main" 
    # ADICIONAMOS AS CHAVES AQUI
    openai_api_key: str
    supabase_url: str
    supabase_key: str

class OrchestratorResponse(BaseModel):
    answer: str
    new_agent: str
    action: str = "respond"

@app.post("/api/v1/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    query_lower = request.query.lower()
    
    if any(word in query_lower for word in ["voltar", "sair", "menu principal", "cancelar"]):
        return OrchestratorResponse(
            answer="Certo, cancelei a operação anterior. Como posso te ajudar agora?",
            new_agent="main",
            action="reset"
        )

    target_agent = request.current_agent

    if target_agent == "main":
        if "atestado" in query_lower:
            target_agent = "atestado"
        elif "consulta" in query_lower or "cadastrar" in query_lower:
            if request.role == "funcionario":
                return OrchestratorResponse(
                    answer="Você não tem permissão para usar comandos de gestão.",
                    new_agent="main"
                )
            target_agent = "tools"
        else:
            target_agent = "rag"

    if target_agent not in AGENTS:
        target_agent = "rag"

    target_url = AGENTS[target_agent]
    logging.info(f"Encaminhando para o agente: {target_agent}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # REPASSANDO O PACOTE COMPLETO PRO RAG (INCLUSIVE CHAVES)
            response = await client.post(target_url, json={
                "query": request.query,
                "tenant_id": request.tenant_id,
                "openai_api_key": request.openai_api_key,
                "supabase_url": request.supabase_url,
                "supabase_key": request.supabase_key
            })
            
            response.raise_for_status()
            agent_data = response.json()
            
            return OrchestratorResponse(
                answer=agent_data.get("answer", "Resposta não encontrada."),
                new_agent=target_agent,
                action="continue"
            )
            
    except httpx.HTTPError as exc:
        logging.error(f"Erro ao contatar o sub-agente {target_agent}: {exc}")
        raise HTTPException(status_code=500, detail=f"O Agente {target_agent} está fora do ar.")