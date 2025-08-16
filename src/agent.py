import asyncio
import socket
import platform
import httpx
import json
import random
from typing import List, Optional
from datetime import datetime
import websockets
import logging
from src.models import HTTPRequestConfig, RequestResult, AgentRegistration, AgentHeartbeat

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, agent_id: str, coordinator_url: str):
        self.agent_id = agent_id
        self.coordinator_url = coordinator_url
        self.hostname = platform.node()
        self.request_config: Optional[HTTPRequestConfig] = None
        self.ws_connection = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = None  # Unlimited retries
        self.base_retry_delay = 1.0  # Start with 1 second
        self.max_retry_delay = 300.0  # Max 5 minutes
        
    def get_ipv6_addresses(self) -> List[str]:
        ipv6_addresses = []
        
        def is_global_ipv6(ip: str) -> bool:
            """Check if an IPv6 address is a global unicast address"""
            # Remove scope id if present
            ip = ip.split('%')[0]
            
            # Filter out non-global addresses
            # Link-local: fe80::/10
            if ip.startswith('fe80:') or ip.startswith('fe8') or ip.startswith('fe9') or ip.startswith('fea') or ip.startswith('feb'):
                return False
            # Loopback: ::1/128
            if ip == '::1' or ip.startswith('::1/'):
                return False
            # Unique Local Addresses (ULA): fc00::/7 (fc00:: - fdff::)
            if ip.startswith('fc') or ip.startswith('fd'):
                return False
            # Multicast: ff00::/8
            if ip.startswith('ff'):
                return False
            # Documentation: 2001:db8::/32
            if ip.startswith('2001:db8:'):
                return False
            # IPv4-mapped IPv6: ::ffff:0:0/96
            if ip.startswith('::ffff:'):
                return False
            
            # Check if it starts with 2 or 3 (global unicast range)
            # Global unicast addresses typically start with 2000::/3 (2000:: - 3fff::)
            if ip.startswith('2') or ip.startswith('3'):
                return True
            
            # Some global addresses might not start with 2 or 3, but let's be conservative
            return False
        
        try:
            # Method 1: Try using netifaces if available
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET6 in addrs:
                        for addr_info in addrs[netifaces.AF_INET6]:
                            ip = addr_info['addr'].split('%')[0]  # Remove scope id if present
                            if is_global_ipv6(ip):
                                ipv6_addresses.append(ip)
            except ImportError:
                # Method 2: Try using ip command (Linux)
                import subprocess
                try:
                    result = subprocess.run(['ip', '-6', 'addr', 'show', 'scope', 'global'], 
                                         capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        import re
                        # Parse IPv6 addresses from ip command output
                        pattern = r'inet6\s+([0-9a-fA-F:]+)/\d+'
                        matches = re.findall(pattern, result.stdout)
                        for ip in matches:
                            if is_global_ipv6(ip):
                                ipv6_addresses.append(ip)
                except (subprocess.SubprocessError, FileNotFoundError):
                    # Method 3: Fall back to socket method but with better handling
                    try:
                        # Try to get all addresses by connecting to an external host
                        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
                            # Use Google's public DNS IPv6
                            s.connect(('2001:4860:4860::8888', 80))
                            local_ip = s.getsockname()[0]
                            if local_ip and is_global_ipv6(local_ip):
                                ipv6_addresses.append(local_ip)
                    except:
                        # Last resort: try hostname resolution
                        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
                            ip = info[4][0]
                            if is_global_ipv6(ip):
                                ipv6_addresses.append(ip)
        except Exception as e:
            logger.error(f"Error getting IPv6 addresses: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_addresses = []
        for ip in ipv6_addresses:
            if ip not in seen:
                seen.add(ip)
                unique_addresses.append(ip)
        
        if not unique_addresses:
            logger.warning("No IPv6 addresses found, using ::1 as fallback")
            unique_addresses = ["::1"]
        else:
            logger.info(f"Found IPv6 addresses: {unique_addresses}")
        
        return unique_addresses
    
    def get_retry_delay(self) -> float:
        if self.reconnect_attempts == 0:
            return 0  # First attempt should be immediate
        
        # Exponential backoff with jitter: base * (2 ^ attempts) + random jitter
        delay = self.base_retry_delay * (2 ** min(self.reconnect_attempts - 1, 8))  # Cap at 2^8
        delay = min(delay, self.max_retry_delay)
        
        # Add jitter (±25% of delay)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        delay += jitter
        
        return max(0, delay)
    
    async def register_with_coordinator(self):
        registration = AgentRegistration(
            agent_id=self.agent_id,
            hostname=self.hostname,
            ipv6_addresses=self.get_ipv6_addresses()
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.coordinator_url}/api/agents/register",
                    json=registration.model_dump()
                )
                if response.status_code == 200:
                    logger.info(f"Successfully registered with coordinator")
                    return True
                else:
                    logger.error(f"Failed to register: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error registering with coordinator: {e}")
            return False
    
    async def execute_request(self, source_ip: str, config: Optional[dict] = None) -> RequestResult:
        # Use provided config or fall back to stored config
        request_config = None
        if config:
            try:
                request_config = HTTPRequestConfig(**config)
            except Exception as e:
                return RequestResult(
                    success=False,
                    error=f"Invalid request configuration: {e}",
                    metadata={
                        "agent_id": self.agent_id,
                        "source_ip": source_ip,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        else:
            request_config = self.request_config
        
        if not request_config:
            return RequestResult(
                success=False,
                error="No request configuration available",
                metadata={
                    "agent_id": self.agent_id,
                    "source_ip": source_ip,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        try:
            transport = httpx.AsyncHTTPTransport(local_address=source_ip)
            async with httpx.AsyncClient(transport=transport) as client:
                response = await client.request(
                    method=request_config.method,
                    url=request_config.url,
                    headers=request_config.headers,
                    params=request_config.params,
                    json=request_config.body if request_config.body else None,
                    timeout=request_config.timeout
                )
                
                return RequestResult(
                    success=True,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text,
                    metadata={
                        "agent_id": self.agent_id,
                        "source_ip": source_ip,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        except Exception as e:
            return RequestResult(
                success=False,
                error=str(e),
                metadata={
                    "agent_id": self.agent_id,
                    "source_ip": source_ip,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    async def handle_message(self, message: str):
        try:
            data = json.loads(message)
            command = data.get("command")
            
            if command == "configure_request":
                self.request_config = HTTPRequestConfig(**data.get("config", {}))
                logger.info("Request configuration updated")
                return {"status": "success", "message": "Configuration updated"}
            
            elif command == "execute_request":
                source_ip = data.get("source_ip")
                config = data.get("config")  # New: support custom config per request
                result = await self.execute_request(source_ip, config)
                return result.model_dump()
            
            elif command == "ping":
                return {"status": "pong", "agent_id": self.agent_id}
            
            else:
                return {"status": "error", "message": f"Unknown command: {command}"}
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def send_heartbeat(self):
        heartbeat = AgentHeartbeat(
            agent_id=self.agent_id,
            ipv6_addresses=self.get_ipv6_addresses(),
            status="active"
        )
        
        if self.ws_connection:
            try:
                await self.ws_connection.send(json.dumps({
                    "type": "heartbeat",
                    "data": heartbeat.model_dump()
                }))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Cannot send heartbeat: WebSocket connection closed")
                raise  # Re-raise to trigger reconnection
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                raise  # Re-raise to trigger reconnection
    
    async def websocket_handler(self):
        ws_url = self.coordinator_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/agent/{self.agent_id}"
        
        while self.running:
            try:
                self.reconnect_attempts += 1
                delay = self.get_retry_delay()
                
                if delay > 0:
                    logger.info(f"Waiting {delay:.1f}s before reconnection attempt {self.reconnect_attempts}")
                    await asyncio.sleep(delay)
                
                if not self.running:
                    break
                
                logger.info(f"Attempting to connect to coordinator (attempt {self.reconnect_attempts})")
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
                    self.ws_connection = websocket
                    self.reconnect_attempts = 0  # Reset on successful connection
                    logger.info(f"Connected to coordinator via WebSocket")
                    
                    # Re-register when reconnecting
                    if not await self.register_with_coordinator():
                        logger.warning("Failed to re-register after reconnection")
                    
                    heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                    
                    try:
                        async for message in websocket:
                            response = await self.handle_message(message)
                            await websocket.send(json.dumps(response))
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed by coordinator")
                    except Exception as e:
                        logger.error(f"Error in WebSocket message handling: {e}")
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                        
            except websockets.exceptions.InvalidURI:
                logger.error(f"Invalid WebSocket URL: {ws_url}")
                break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
            except (ConnectionRefusedError, OSError) as e:
                logger.warning(f"Coordinator unavailable: {e}")
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
            
            # Clean up connection reference on any error
            self.ws_connection = None
    
    async def heartbeat_loop(self):
        while self.running:
            try:
                await self.send_heartbeat()
                await asyncio.sleep(30)
            except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError):
                logger.warning("Heartbeat failed due to connection issue")
                break  # Exit heartbeat loop to trigger reconnection
            except Exception as e:
                logger.error(f"Unexpected error in heartbeat loop: {e}")
                await asyncio.sleep(30)  # Continue heartbeat despite other errors
    
    async def run(self):
        self.running = True
        logger.info(f"Starting agent {self.agent_id}")
        
        # Try initial registration, but proceed to websocket handler regardless
        # The websocket handler will handle re-registration on connection
        initial_registration = await self.register_with_coordinator()
        if initial_registration:
            logger.info("Initial registration successful")
            self.reconnect_attempts = 0  # Reset since initial connection worked
        else:
            logger.warning("Initial registration failed, will retry during WebSocket connection")
        
        await self.websocket_handler()
    
    async def stop(self):
        self.running = False
        if self.ws_connection:
            await self.ws_connection.close()