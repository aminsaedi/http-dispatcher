from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    mode: str = "coordinator"
    
    coordinator_host: str = "0.0.0.0"
    coordinator_port: int = 8000
    coordinator_url: str = "http://localhost:8000"
    
    agent_id: Optional[str] = None
    
    log_level: str = "INFO"
    
    class Config:
        env_prefix = "DISPATCHER_"
        env_file = ".env"


settings = Settings()