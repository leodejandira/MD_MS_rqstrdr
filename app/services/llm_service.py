import logging
from openai import AsyncOpenAI # Usando a versão Async nativa da OpenAI

logger = logging.getLogger(__name__)

AGENT_DESCRIPTIONS = {
    "rag": "Use para dúvidas institucionais, manuais de RH, cultura da empresa e políticas gerais.",
    "tools": "Use para ações no banco de dados (férias, atestados, contratação) OU quando o usuário estiver confirmando que os dados de um documento/atestado estão corretos para serem salvos (ex: dizendo 'sim', 'correto', 'pode salvar').",
    "docs": "Use EXCLUSIVAMENTE quando o usuário enviar um link/URL de imagem ou documento informando que é um atestado médico para leitura."
}

async def classificar_intencao(historico: list, api_key: str) -> str:
    try:
        client = AsyncOpenAI(api_key=api_key)
        contexto_str = "\n".join([f"{'Usuário' if msg['role'] == 'user' else 'Assistente'}: {msg['content']}" for msg in historico])
        
        # PROMPT BLINDADO: Regra de ouro para links
        prompt = f"""Você é um roteador de requisições de um sistema de RH.
        Analise o histórico da conversa e decida qual agente deve processar a ÚLTIMA mensagem.
        
        REGRA DE OURO 1: Se a última mensagem contiver uma URL (http/https), roteie para 'docs'.
        REGRA DE OURO 2: Se o assistente acabou de perguntar se os dados do atestado estão corretos e o usuário respondeu afirmativamente (ex: 'sim', 'está certo'), roteie OBRIGATORIAMENTE para 'tools' para que os dados sejam salvos.
        
        Agentes disponíveis:
        {AGENT_DESCRIPTIONS}
        
        Histórico recente da conversa:
        {contexto_str}
        
        Responda APENAS com a chave do agente escolhido (rag, tools ou docs)."""
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.0 
        )
        
        rota = response.choices[0].message.content.strip().lower()
        return rota if rota in ["rag", "tools", "docs"] else "rag"
        
    except Exception as e:
        logger.error(f"[LLM ERROR] Erro no Roteador Semântico: {e}")
        return "rag"