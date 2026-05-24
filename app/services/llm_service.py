import logging
from openai import AsyncOpenAI # Usando a versão Async nativa da OpenAI

logger = logging.getLogger(__name__)

AGENT_DESCRIPTIONS = {
    "rag": "Use para dúvidas institucionais, manuais de RH, cultura da empresa e políticas gerais.",
    "tools": "Use para consultas de dados específicos de funcionários no banco de dados (férias, atestados, contratação, cargo)."
}

async def classificar_intencao(historico: list, api_key: str) -> str:
    """Roteador Semântico: Analisa o histórico e decide para qual agente enviar."""
    try:
        client = AsyncOpenAI(api_key=api_key)
        contexto_str = "\n".join([f"{'Usuário' if msg['role'] == 'user' else 'Assistente'}: {msg['content']}" for msg in historico])
        
        prompt = f"""Você é um roteador de requisições de um sistema de RH.
        Analise o histórico da conversa e decida qual agente deve processar a ÚLTIMA mensagem.
        
        Agentes disponíveis:
        {AGENT_DESCRIPTIONS}
        
        Histórico recente da conversa:
        {contexto_str}
        
        Responda APENAS com a chave do agente escolhido (rag ou tools)."""
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.0
        )
        
        rota = response.choices[0].message.content.strip().lower()
        return rota if rota in ["rag", "tools"] else "rag"
        
    except Exception as e:
        logger.error(f"[LLM ERROR] Falha no roteador semântico: {e}")
        return "rag"