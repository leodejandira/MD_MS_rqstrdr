from pydantic import BaseModel

class OrchestratorRequest(BaseModel):
    query: str
    tenant_id: int
    usuario_id: str
    role: str  
    current_agent: str = "main" 
    openai_api_key: str
    supabase_url: str
    supabase_key: str

class OrchestratorResponse(BaseModel):
    answer: str
    new_agent: str
    action: str = "respond"