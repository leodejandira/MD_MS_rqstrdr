import httpx
import logging

logger = logging.getLogger(__name__)

async def buscar_contexto_conversa(usuario_id: str, tenant_id: int, supa_url: str, supa_key: str, limite: int = 6) -> list:
    """Busca o histórico recente filtrando diretamente pelo UUID do usuário corporativo."""
    try:
        endpoint = f"{supa_url}/rest/v1/historico_conversas"
        headers = {
            "apikey": supa_key,
            "Authorization": f"Bearer {supa_key}",
            "Content-Type": "application/json"
        }
        params = {
            "usuario_id": f"eq.{usuario_id}", 
            "tenant_id": f"eq.{tenant_id}",
            "select": "role,content",
            "order": "created_at.desc",
            "limit": limite
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            dados = response.json()
            return dados[::-1] 
            
    except Exception as e:
        logger.error(f"[DB ERROR] Falha ao buscar contexto por usuário: {e}")
        return []

async def salvar_mensagem_historico(usuario_id: str, tenant_id: int, role: str, content: str, supa_url: str, supa_key: str):
    """Vincula a nova interação ao UUID do usuário para fins de histórico e análise Pulse."""
    try:
        endpoint = f"{supa_url}/rest/v1/historico_conversas"
        headers = {
            "apikey": supa_key,
            "Authorization": f"Bearer {supa_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal" 
        }
        payload = {
            "usuario_id": usuario_id,
            "tenant_id": tenant_id,
            "role": role,
            "content": content
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
    except Exception as e:
        logger.error(f"[DB ERROR] Falha ao salvar mensagem por usuário: {e}")