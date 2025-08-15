from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class HTTPRequestConfig(BaseModel):
    url: str
    method: HTTPMethod = HTTPMethod.GET
    headers: Dict[str, str] = Field(default_factory=dict)
    params: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    timeout: float = 30.0


class AgentInfo(BaseModel):
    agent_id: str
    hostname: str
    ipv6_addresses: List[str]
    last_seen: datetime
    status: str = "active"
    requests_processed: int = 0


class IPStatus(BaseModel):
    ip: str
    agent_id: str
    last_used: Optional[datetime] = None
    requests_count: int = 0
    status: str = "available"


class RequestResult(BaseModel):
    success: bool
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentRegistration(BaseModel):
    agent_id: str
    hostname: str
    ipv6_addresses: List[str]


class AgentHeartbeat(BaseModel):
    agent_id: str
    ipv6_addresses: List[str]
    status: str = "active"