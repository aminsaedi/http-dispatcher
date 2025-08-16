import asyncio
import json
import uuid
import uvicorn
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, Response
import logging
from collections import deque
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from src.models import (
    AgentInfo, HTTPRequestConfig, RequestResult, 
    AgentRegistration, IPStatus, ExecuteRequest
)

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.agent_connections: Dict[str, WebSocket] = {}
        self.agent_response_queues: Dict[str, asyncio.Queue] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}  # Track pending requests by ID
        self.ip_pool: List[IPStatus] = []
        self.request_config: Optional[HTTPRequestConfig] = None
        self.round_robin_index = 0
        self.request_history = deque(maxlen=1000)
        self.app = FastAPI(title="HTTP Dispatcher Coordinator")
        self.start_time = datetime.utcnow()
        
        # Prometheus metrics
        self.setup_metrics()
        self.setup_routes()
    
    def setup_metrics(self):
        # Define Prometheus metrics
        self.metrics = {
            'requests_total': Counter('http_dispatcher_requests_total', 'Total number of requests executed', ['agent_id', 'status_code', 'method']),
            'requests_duration': Histogram('http_dispatcher_request_duration_seconds', 'Request duration in seconds', ['agent_id', 'method'], buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]),
            'agents_connected': Gauge('http_dispatcher_agents_connected', 'Number of connected agents'),
            'agents_total': Gauge('http_dispatcher_agents_total', 'Total number of registered agents'),
            'ip_pool_size': Gauge('http_dispatcher_ip_pool_size', 'Size of the IP pool'),
            'ip_pool_available': Gauge('http_dispatcher_ip_pool_available', 'Number of available IPs in pool'),
            'websocket_connections': Gauge('http_dispatcher_websocket_connections', 'Number of active WebSocket connections'),
            'request_errors': Counter('http_dispatcher_request_errors_total', 'Total number of request errors', ['agent_id', 'error_type']),
            'agent_requests': Counter('http_dispatcher_agent_requests_total', 'Total requests per agent', ['agent_id']),
            'response_size_bytes': Histogram('http_dispatcher_response_size_bytes', 'Response size in bytes', ['agent_id'], buckets=[100, 1000, 10000, 100000, 1000000]),
            'queue_depth': Gauge('http_dispatcher_queue_depth', 'Number of pending requests in queue', ['agent_id']),
            'uptime_seconds': Gauge('http_dispatcher_uptime_seconds', 'Coordinator uptime in seconds'),
        }
    
    def setup_routes(self):
        @self.app.post("/api/agents/register")
        async def register_agent(registration: AgentRegistration):
            agent_info = AgentInfo(
                agent_id=registration.agent_id,
                hostname=registration.hostname,
                ipv6_addresses=registration.ipv6_addresses,
                last_seen=datetime.utcnow(),
                status="active"
            )
            
            self.agents[registration.agent_id] = agent_info
            self.update_ip_pool(registration.agent_id, registration.ipv6_addresses)
            
            # Update metrics
            self.update_metrics()
            
            logger.info(f"Agent {registration.agent_id} registered with {len(registration.ipv6_addresses)} IPv6 addresses")
            return {"status": "success", "message": "Agent registered successfully"}
        
        @self.app.websocket("/ws/agent/{agent_id}")
        async def websocket_endpoint(websocket: WebSocket, agent_id: str):
            await websocket.accept()
            self.agent_connections[agent_id] = websocket
            
            # Create a queue for pending responses for this agent
            self.agent_response_queues[agent_id] = asyncio.Queue()
            
            try:
                while True:
                    data = await websocket.receive_text()
                    # Check if this is a response to a request
                    try:
                        msg = json.loads(data)
                        if msg.get("type") == "heartbeat":
                            await self.handle_agent_message(agent_id, data)
                        else:
                            # Check if this is a response to a pending request
                            request_id = msg.get("request_id")
                            if request_id and request_id in self.pending_requests:
                                # This is a response to a specific request
                                future = self.pending_requests[request_id]
                                if not future.done():
                                    future.set_result(data)
                                del self.pending_requests[request_id]
                            else:
                                # Fallback: put it in the queue as before
                                await self.agent_response_queues[agent_id].put(data)
                    except json.JSONDecodeError:
                        # If it's not JSON, put it in the queue as a response
                        await self.agent_response_queues[agent_id].put(data)
            except WebSocketDisconnect:
                logger.info(f"Agent {agent_id} disconnected")
                if agent_id in self.agent_connections:
                    del self.agent_connections[agent_id]
                if agent_id in self.agent_response_queues:
                    del self.agent_response_queues[agent_id]
                if agent_id in self.agents:
                    self.agents[agent_id].status = "disconnected"
        
        @self.app.get("/api/agents")
        async def get_agents():
            return {"agents": [agent.model_dump() for agent in self.agents.values()]}
        
        @self.app.get("/api/pool/status")
        async def get_pool_status():
            return {
                "total_ips": len(self.ip_pool),
                "active_agents": len([a for a in self.agents.values() if a.status == "active"]),
                "ip_pool": [ip.model_dump() for ip in self.ip_pool]
            }
        
        @self.app.post("/api/config/request")
        async def configure_request(config: HTTPRequestConfig):
            self.request_config = config
            await self.broadcast_config_to_agents()
            return {"status": "success", "message": "Request configuration updated and propagated"}
        
        @self.app.get("/api/config/request")
        async def get_request_config():
            if not self.request_config:
                raise HTTPException(status_code=404, detail="No request configuration available")
            return self.request_config.model_dump()
        
        @self.app.post("/api/execute")
        async def execute_request(execute_config: ExecuteRequest):
            if not self.ip_pool:
                raise HTTPException(status_code=400, detail="No IP addresses available in pool")
            
            result = await self.execute_with_round_robin(execute_config)
            return result
        
        @self.app.get("/api/history")
        async def get_request_history(limit: int = 100):
            history = list(self.request_history)[-limit:]
            return {"history": history}
        
        @self.app.delete("/api/agents/{agent_id}")
        async def remove_agent(agent_id: str):
            if agent_id in self.agents:
                del self.agents[agent_id]
                if agent_id in self.agent_connections:
                    await self.agent_connections[agent_id].close()
                    del self.agent_connections[agent_id]
                
                self.ip_pool = [ip for ip in self.ip_pool if ip.agent_id != agent_id]
                return {"status": "success", "message": f"Agent {agent_id} removed"}
            else:
                raise HTTPException(status_code=404, detail="Agent not found")
        
        @self.app.get("/api/stats")
        async def get_stats():
            total_requests = sum(ip.requests_count for ip in self.ip_pool)
            return {
                "total_agents": len(self.agents),
                "active_agents": len([a for a in self.agents.values() if a.status == "active"]),
                "total_ips": len(self.ip_pool),
                "total_requests_processed": total_requests,
                "agents": {
                    agent_id: {
                        "hostname": agent.hostname,
                        "ipv6_count": len(agent.ipv6_addresses),
                        "requests_processed": agent.requests_processed,
                        "status": agent.status
                    }
                    for agent_id, agent in self.agents.items()
                }
            }
        
        @self.app.get("/metrics")
        async def get_metrics():
            # Update metrics before returning
            self.update_metrics()
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    def update_ip_pool(self, agent_id: str, ipv6_addresses: List[str]):
        self.ip_pool = [ip for ip in self.ip_pool if ip.agent_id != agent_id]
        
        for ip in ipv6_addresses:
            ip_status = IPStatus(
                ip=ip,
                agent_id=agent_id,
                status="available"
            )
            self.ip_pool.append(ip_status)
    
    def update_metrics(self):
        # Update gauge metrics
        active_agents = len([a for a in self.agents.values() if a.status == "active"])
        available_ips = len([ip for ip in self.ip_pool if ip.status == "available"])
        
        self.metrics['agents_connected'].set(len(self.agent_connections))
        self.metrics['agents_total'].set(len(self.agents))
        self.metrics['ip_pool_size'].set(len(self.ip_pool))
        self.metrics['ip_pool_available'].set(available_ips)
        self.metrics['websocket_connections'].set(len(self.agent_connections))
        
        # Update uptime
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        self.metrics['uptime_seconds'].set(uptime)
        
        # Update queue depths
        for agent_id, queue in self.agent_response_queues.items():
            self.metrics['queue_depth'].labels(agent_id=agent_id).set(queue.qsize())
    
    async def handle_agent_message(self, agent_id: str, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "heartbeat":
                heartbeat_data = data.get("data", {})
                if agent_id in self.agents:
                    self.agents[agent_id].last_seen = datetime.utcnow()
                    self.agents[agent_id].status = "active"
                    self.update_ip_pool(agent_id, heartbeat_data.get("ipv6_addresses", []))
            
        except Exception as e:
            logger.error(f"Error handling agent message: {e}")
    
    async def broadcast_config_to_agents(self):
        if not self.request_config:
            return
        
        message = json.dumps({
            "command": "configure_request",
            "config": self.request_config.model_dump()
        })
        
        disconnected = []
        for agent_id, ws in self.agent_connections.items():
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send config to agent {agent_id}: {e}")
                disconnected.append(agent_id)
        
        for agent_id in disconnected:
            del self.agent_connections[agent_id]
            if agent_id in self.agents:
                self.agents[agent_id].status = "disconnected"
    
    async def execute_with_round_robin(self, execute_config: ExecuteRequest) -> Dict:
        available_ips = [ip for ip in self.ip_pool if ip.status == "available"]
        
        if not available_ips:
            raise HTTPException(status_code=503, detail="No available IPs in pool")
        
        self.round_robin_index = self.round_robin_index % len(available_ips)
        selected_ip = available_ips[self.round_robin_index]
        self.round_robin_index += 1
        
        agent_id = selected_ip.agent_id
        
        if agent_id not in self.agent_connections:
            selected_ip.status = "unavailable"
            raise HTTPException(status_code=503, detail=f"Agent {agent_id} is not connected")
        
        if not hasattr(self, 'agent_response_queues') or agent_id not in self.agent_response_queues:
            raise HTTPException(status_code=503, detail=f"Agent {agent_id} response queue not initialized")
        
        # Generate unique request ID to match request with response
        request_id = str(uuid.uuid4())
        
        message = json.dumps({
            "command": "execute_request",
            "request_id": request_id,
            "source_ip": selected_ip.ip,
            "config": execute_config.model_dump()
        })
        
        try:
            ws = self.agent_connections[agent_id]
            
            # Create a future for this specific request
            future = asyncio.Future()
            self.pending_requests[request_id] = future
            
            await ws.send_text(message)
            
            # Wait for the specific response using the future
            start_time = datetime.utcnow()
            try:
                response_text = await asyncio.wait_for(future, timeout=35.0)
                response = json.loads(response_text)
            except asyncio.TimeoutError:
                # Clean up the pending request on timeout
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                # Track timeout error
                self.metrics['request_errors'].labels(agent_id=agent_id, error_type='timeout').inc()
                raise
            
            # Track request metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            status_code = response.get("status_code", "unknown")
            method = execute_config.method
            
            self.metrics['requests_total'].labels(
                agent_id=agent_id, 
                status_code=str(status_code), 
                method=method
            ).inc()
            self.metrics['requests_duration'].labels(
                agent_id=agent_id, 
                method=method
            ).observe(duration)
            self.metrics['agent_requests'].labels(agent_id=agent_id).inc()
            
            # Track response size
            response_body = response.get("body", "")
            if response_body:
                response_size = len(str(response_body).encode('utf-8'))
                self.metrics['response_size_bytes'].labels(agent_id=agent_id).observe(response_size)
            
            # Track errors if request failed
            if not response.get("success", False):
                error_type = "request_failed"
                if response.get("error"):
                    error_type = response.get("error", "unknown_error")[:50]  # Limit label length
                self.metrics['request_errors'].labels(agent_id=agent_id, error_type=error_type).inc()
            
            # Extract the actual source IP used by the agent from the response metadata
            actual_source_ip = response.get("metadata", {}).get("source_ip", selected_ip.ip)
            
            # Update the IP status with the actual IP used
            for ip in self.ip_pool:
                if ip.ip == actual_source_ip and ip.agent_id == agent_id:
                    ip.last_used = datetime.utcnow()
                    ip.requests_count += 1
                    break
            
            if agent_id in self.agents:
                self.agents[agent_id].requests_processed += 1
            
            # Return the agent's response directly without wrapping it
            # The agent already includes all necessary metadata
            self.request_history.append(response)
            return response
            
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Request timeout")
        except Exception as e:
            logger.error(f"Error executing request: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def cleanup_inactive_agents(self):
        while True:
            await asyncio.sleep(60)
            now = datetime.utcnow()
            for agent_id, agent in list(self.agents.items()):
                if agent.status == "active" and (now - agent.last_seen) > timedelta(minutes=2):
                    agent.status = "inactive"
                    logger.warning(f"Agent {agent_id} marked as inactive")
    
    def get_app(self):
        return self.app
    
    async def start_servers(self, bind_addresses: List[Tuple[str, int]]):
        """Start multiple uvicorn servers on different bind addresses"""
        if not bind_addresses:
            raise ValueError("At least one bind address must be provided")
        
        logger.info(f"Starting coordinator on {len(bind_addresses)} bind addresses: {bind_addresses}")
        
        # Create cleanup task
        cleanup_task = asyncio.create_task(self.cleanup_inactive_agents())
        
        # Create server tasks for each bind address
        server_tasks = []
        servers = []
        
        for host, port in bind_addresses:
            config = uvicorn.Config(
                app=self.get_app(),
                host=host,
                port=port,
                log_level="warning"  # Reduce uvicorn noise
            )
            server = uvicorn.Server(config)
            servers.append(server)
            server_task = asyncio.create_task(server.serve())
            server_tasks.append(server_task)
            logger.info(f"Started server on {host}:{port}")
        
        try:
            # Wait for all servers to complete
            await asyncio.gather(*server_tasks)
        except Exception as e:
            logger.error(f"Error in server tasks: {e}")
        finally:
            # Cleanup
            cleanup_task.cancel()
            for server in servers:
                if hasattr(server, 'should_exit'):
                    server.should_exit = True