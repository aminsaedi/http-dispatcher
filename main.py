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
              default='coordinator', help='Mode to run the application in')
@click.option('--coordinator-url', default='http://localhost:8000', 
              help='URL of the coordinator (for agent and monitoring modes)')
@click.option('--agent-id', default=None, help='Agent ID (auto-generated if not provided)')
@click.option('--host', default='0.0.0.0', help='Host to bind the coordinator to')
@click.option('--port', default=8000, type=int, help='Port to bind the coordinator to')
def main(mode, coordinator_url, agent_id, host, port):
    """HTTP Dispatcher - Distributed HTTP request system with IPv6 support"""
    
    # Setup logging based on mode
    setup_logging(mode)
    
    if mode == 'coordinator':
        logger.info("Starting Coordinator mode")
        coordinator = Coordinator()
        
        async def start_coordinator():
            cleanup_task = asyncio.create_task(coordinator.cleanup_inactive_agents())
            try:
                config = uvicorn.Config(
                    app=coordinator.get_app(),
                    host=host,
                    port=port,
                    log_level=settings.log_level.lower()
                )
                server = uvicorn.Server(config)
                await server.serve()
            finally:
                cleanup_task.cancel()
        
        asyncio.run(start_coordinator())
    
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
        logger.info("Starting Monitoring mode")
        app = MonitoringApp(coordinator_url)
        app.run()


if __name__ == '__main__':
    main()