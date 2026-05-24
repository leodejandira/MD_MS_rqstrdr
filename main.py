from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import logging
from openai import OpenAI
from supabase import create_client, Client

app = FastAPI(title="MindDesk - Orquestrador de Agentes")
logging.basicConfig(level=logging.INFO)

AGENTS = {
    "rag": "http://host.docker.internal:8000/api/v1/ask",
    "tools": "http://host.docker.internal:8040/api/v1/executar"
}

AGENT_DESCRIPTIONS = {
    "rag": "Use para dúvidas institucionais, manuais de RH, cultura da empresa e políticas gerais.",
    "tools": "Use para consultas de dados específicos de funcionários no banco de dados (férias, atestados, contratação, cargo)."
}

class OrchestratorRequest(BaseModel):
    query: str
    tenant_id: int
    user_id: str
    role: str  
    current_agent: str = "main" 
    session_id: str
    openai_api_key: str
    supabase_url: str
    supabase_key: str

class OrchestratorResponse(BaseModel):
    answer: str
    new_agent: str
    action: str = "respond"


def classificar_intencao(historico: list, api_key: str) -> str:
    try:
        client = OpenAI(api_key=api_key)
        
        # Transforma o histórico em um texto fácil pra IA ler
        contexto_str = "\n".join([f"{'Usuário' if msg['role'] == 'user' else 'Assistente'}: {msg['content']}" for msg in historico])
        
        prompt = f"""Você é um roteador de requisições de um sistema de RH.
        Analise o histórico da conversa e decida qual agente deve processar a ÚLTIMA mensagem.
        
        Agentes disponíveis:
        {AGENT_DESCRIPTIONS}
        
        Histórico recente da conversa:
        {contexto_str}
        
        Responda APENAS com a chave do agente escolhido (rag ou tools). Não escreva mais nada."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.0
        )
        
        rota = response.choices[0].message.content.strip().lower()
        if rota in AGENTS:
            return rota
        return "rag" 
        
    except Exception as e:
        logging.error(f"Erro no roteador semântico: {e}")
        return "rag"
    
# AS NOVAS FUNÇÕES 100% HTTP REST - ADEUS BUG DO PROXY
def buscar_contexto_conversa(session_id: str, tenant_id: int, supa_url: str, supa_key: str, limite: int = 6):
    try:
        # A URL padrão da API REST do Supabase para a tabela historico_conversas
        endpoint = f"{supa_url}/rest/v1/historico_conversas"
        
        headers = {
            "apikey": supa_key,
            "Authorization": f"Bearer {supa_key}",
            "Content-Type": "application/json"
        }
        
        # Parâmetros: Filtra por session e tenant, ordena decrescente e limita
        params = {
            "session_id": f"eq.{session_id}",
            "tenant_id": f"eq.{tenant_id}",
            "select": "role,content",
            "order": "created_at.desc",
            "limit": limite
        }
        
        # Faz a chamada SÍNCRONA usando httpx 
        with httpx.Client() as client:
            response = client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            
            dados = response.json()
            return dados[::-1] # Inverte pra ficar na ordem certa
            
    except Exception as e:
        print(f"[HISTORICO ERROR] {e}")
        return []

def salvar_mensagem_historico(session_id: str, tenant_id: int, role: str, content: str, supa_url: str, supa_key: str):
    try:
        endpoint = f"{supa_url}/rest/v1/historico_conversas"
        headers = {
            "apikey": supa_key,
            "Authorization": f"Bearer {supa_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal" # Fala pro Supabase não devolver o dado de volta (economiza banda)
        }
        
        payload = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "role": role,
            "content": content
        }
        
        with httpx.Client() as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
    except Exception as e:
        print(f"[HISTORICO SAVE ERROR] {e}")

@app.post("/api/v1/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    query_lower = request.query.lower()
    
    if any(word in query_lower for word in ["voltar", "sair", "menu principal", "cancelar"]):
        return OrchestratorResponse(answer="Certo, cancelei a operação. Como posso te ajudar?", new_agent="main", action="reset")

    # 1. SALVA A PERGUNTA ATUAL NO BANCO
    salvar_mensagem_historico(request.session_id, request.tenant_id, "user", request.query, request.supabase_url, request.supabase_key)

    # 2. BUSCA O CONTEXTO INTEIRO (que agora já inclui a pergunta acima)
    historico = buscar_contexto_conversa(request.session_id, request.tenant_id, request.supabase_url, request.supabase_key)

    target_agent = request.current_agent

    if target_agent == "main":
        # Manda o histórico pro roteador semântico!
        target_agent = classificar_intencao(historico, request.openai_api_key)
        logging.info(f"IA Roteadora escolheu o agente: {target_agent}")

        if target_agent == "tools" and request.role == "funcionario":
            return OrchestratorResponse(answer="Você não tem permissão para usar consultas de base.", new_agent="main")

    if target_agent not in AGENTS:
        target_agent = "rag"

    target_url = AGENTS[target_agent]
    
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(target_url, json={
                "query": request.query,
                "tenant_id": request.tenant_id,
                "openai_api_key": request.openai_api_key,
                "supabase_url": request.supabase_url,
                "supabase_key": request.supabase_key,
                "history": historico # <--- MANDANDO A FOFOCA PRO TOOLS/RAG!
            })
            
            response.raise_for_status()
            agent_data = response.json()
            answer = agent_data.get("answer", "Resposta não encontrada.")
            
            # 3. SALVA A RESPOSTA DA IA NO BANCO ANTES DE DEVOLVER
            salvar_mensagem_historico(request.session_id, request.tenant_id, "assistant", answer, request.supabase_url, request.supabase_key)
            
            return OrchestratorResponse(answer=answer, new_agent=target_agent, action="continue")
            
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=500, detail=f"Erro no Agente {target_agent}: {exc}")