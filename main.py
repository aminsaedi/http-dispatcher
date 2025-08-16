#!/usr/bin/env python3
import asyncio
import click
import logging
import uvicorn
import uuid
import sys
from src.config import settings
from src.agent import Agent
from src.coordinator import Coordinator
from src.monitoring import MonitoringApp

# Configure logging based on mode
def setup_logging(mode: str):
    if mode == 'monitoring':
        # For monitoring mode, disable all logging or redirect to file
        logging.basicConfig(
            level=logging.CRITICAL,  # Only show critical errors
            filename='/tmp/http-dispatcher-monitoring.log',
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # For other modes, use normal console logging
        logging.basicConfig(
            level=getattr(logging, settings.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

logger = logging.getLogger(__name__)


@click.command()
@click.option('--mode', type=click.Choice(['agent', 'coordinator', 'monitoring']), 
              default='coordinator', help='Mode to run the application in (monitoring mode deprecated)')
@click.option('--coordinator-url', default='http://localhost:8000', 
              help='URL of the coordinator (for agent and monitoring modes)')
@click.option('--agent-id', default=None, help='Agent ID (auto-generated if not provided)')
@click.option('--host', default='0.0.0.0', help='Host to bind the coordinator to')
@click.option('--port', default=8000, type=int, help='Port to bind the coordinator to')
@click.option('--bind', multiple=True, help='Additional bind addresses in format host:port (can be used multiple times)')
def main(mode, coordinator_url, agent_id, host, port, bind):
    """HTTP Dispatcher - Distributed HTTP request system with IPv6 support"""
    
    # Setup logging based on mode
    setup_logging(mode)
    
    if mode == 'coordinator':
        logger.info("Starting Coordinator mode")
        coordinator = Coordinator()
        
        # Build list of bind addresses
        bind_addresses = [(host, port)]  # Always include the default host:port
        
        # Parse additional bind addresses
        for bind_addr in bind:
            try:
                if ':' in bind_addr:
                    bind_host, bind_port = bind_addr.rsplit(':', 1)
                    bind_addresses.append((bind_host, int(bind_port)))
                else:
                    # If no port specified, use the same port as default
                    bind_addresses.append((bind_addr, port))
            except ValueError as e:
                logger.error(f"Invalid bind address '{bind_addr}': {e}")
                sys.exit(1)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_bind_addresses = []
        for addr in bind_addresses:
            if addr not in seen:
                seen.add(addr)
                unique_bind_addresses.append(addr)
        
        asyncio.run(coordinator.start_servers(unique_bind_addresses))
    
    elif mode == 'agent':
        if not agent_id:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Starting Agent mode with ID: {agent_id}")
        agent = Agent(agent_id, coordinator_url)
        
        try:
            asyncio.run(agent.run())
        except KeyboardInterrupt:
            logger.info("Agent shutting down...")
            asyncio.run(agent.stop())
    
    elif mode == 'monitoring':
        logger.warning("⚠️  Monitoring mode is deprecated! Use Docker Compose with Grafana instead.")
        logger.info("Starting legacy Monitoring mode")
        app = MonitoringApp(coordinator_url)
        app.run()


if __name__ == '__main__':
    main()