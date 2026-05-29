from fastapi import APIRouter, HTTPException
import logging

from core.schemas import OrchestratorRequest, OrchestratorResponse
from services.db_service import buscar_contexto_conversa, salvar_mensagem_historico
from services.llm_service import classificar_intencao
from services.agent_service import repassar_para_agente

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    query_lower = request.query.lower()
    
    if any(word in query_lower for word in ["voltar", "sair", "menu principal", "cancelar"]):
        return OrchestratorResponse(answer="Certo, cancelei a operação. Como posso te ajudar?", new_agent="main", action="reset")

    # Persistência e busca baseadas no identificador único do funcionário
    await salvar_mensagem_historico(request.usuario_id, request.tenant_id, "user", request.query, request.supabase_url, request.supabase_key)
    historico = await buscar_contexto_conversa(request.usuario_id, request.tenant_id, request.supabase_url, request.supabase_key)

    target_agent = request.current_agent
    if target_agent == "main":
        target_agent = await classificar_intencao(historico, request.openai_api_key)
        logger.info(f"Rota escolhida: {target_agent}")

        if target_agent == "tools" and request.role == "funcionario":
            return OrchestratorResponse(answer="Você não tem permissão para usar consultas de base.", new_agent="main")

    payload_to_agent = {
        "query": request.query,
        "tenant_id": request.tenant_id,
        "user_id": request.usuario_id,
        "openai_api_key": request.openai_api_key,
        "supabase_url": request.supabase_url,
        "supabase_key": request.supabase_key,
        "history": historico 
    }
    answer = await repassar_para_agente(target_agent, payload_to_agent)
    
    await salvar_mensagem_historico(request.usuario_id, request.tenant_id, "assistant", answer, request.supabase_url, request.supabase_key)
    
    return OrchestratorResponse(answer=answer, new_agent=target_agent, action="continue")