from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Button, Input, Label, TabbedContent, TabPane
from textual.reactive import reactive
from textual import work
import httpx
import asyncio
from datetime import datetime
import json
from typing import Optional, Dict, List, Any


class MonitoringApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    .status-box {
        border: solid green;
        padding: 1;
        margin: 1;
        height: auto;
    }
    
    .error {
        color: red;
    }
    
    .success {
        color: green;
    }
    
    .info-panel {
        border: solid blue;
        padding: 1;
        margin: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    .config-input {
        margin: 1;
    }
    
    .execute-button {
        margin: 1;
        width: 30;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("e", "execute_request", "Execute Request"),
        ("c", "configure", "Configure Request"),
    ]
    
    def __init__(self, coordinator_url: str):
        super().__init__()
        self.coordinator_url = coordinator_url
        self.agents_data: List[Dict] = []
        self.pool_status: Dict = {}
        self.stats: Dict = {}
        self.last_result: Optional[Dict] = None
        self.refresh_task = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        
        with TabbedContent():
            with TabPane("Overview", id="overview"):
                with Horizontal():
                    with Vertical():
                        yield Static("System Status", classes="status-box")
                        self.status_widget = Static("Loading...", id="status")
                        yield self.status_widget
                        
                        yield Static("Statistics", classes="info-panel")
                        self.stats_widget = Static("", id="stats")
                        yield self.stats_widget
                    
                    with Vertical():
                        yield Static("Last Request Result", classes="info-panel")
                        self.result_widget = Static("No requests executed yet", id="result")
                        yield self.result_widget
            
            with TabPane("Agents", id="agents"):
                self.agents_table = DataTable()
                self.agents_table.add_columns("Agent ID", "Hostname", "IPv6 Count", "Status", "Requests", "Last Seen")
                yield self.agents_table
            
            with TabPane("IP Pool", id="pool"):
                self.pool_table = DataTable()
                self.pool_table.add_columns("IP Address", "Agent ID", "Status", "Requests", "Last Used")
                yield self.pool_table
            
            with TabPane("Configuration", id="config"):
                with Vertical():
                    yield Label("HTTP Request Configuration")
                    yield Label("URL:")
                    self.url_input = Input(placeholder="https://example.com/api", classes="config-input")
                    yield self.url_input
                    
                    yield Label("Method:")
                    self.method_input = Input(value="GET", classes="config-input")
                    yield self.method_input
                    
                    yield Label("Headers (JSON):")
                    self.headers_input = Input(placeholder='{"User-Agent": "HTTP-Dispatcher"}', classes="config-input")
                    yield self.headers_input
                    
                    yield Label("Timeout (seconds):")
                    self.timeout_input = Input(value="30", classes="config-input")
                    yield self.timeout_input
                    
                    with Horizontal():
                        yield Button("Save Configuration", id="save-config", classes="execute-button")
                        yield Button("Load Current", id="load-config", classes="execute-button")
            
            with TabPane("Execute", id="execute"):
                with Vertical():
                    yield Button("Execute Request", id="execute-btn", variant="primary", classes="execute-button")
                    self.execute_result = Static("", id="exec-result")
                    yield self.execute_result
            
            with TabPane("History", id="history"):
                self.history_table = DataTable()
                self.history_table.add_columns("Timestamp", "Agent", "IP", "Status", "Status Code")
                yield self.history_table
    
    async def on_mount(self) -> None:
        self.refresh_task = self.set_interval(5, self.action_refresh)
        self.action_refresh()
    
    async def refresh_data(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                agents_response = await client.get(f"{self.coordinator_url}/api/agents")
                self.agents_data = agents_response.json().get("agents", [])
                
                pool_response = await client.get(f"{self.coordinator_url}/api/pool/status")
                self.pool_status = pool_response.json()
                
                stats_response = await client.get(f"{self.coordinator_url}/api/stats")
                self.stats = stats_response.json()
                
                history_response = await client.get(f"{self.coordinator_url}/api/history?limit=50")
                self.history_data = history_response.json().get("history", [])
            
            self.update_display()
        except Exception as e:
            self.status_widget.update(f"Error: {e}")
    
    def update_display(self):
        status_text = f"Active Agents: {self.pool_status.get('active_agents', 0)}\n"
        status_text += f"Total IPs: {self.pool_status.get('total_ips', 0)}\n"
        self.status_widget.update(status_text)
        
        stats_text = f"Total Agents: {self.stats.get('total_agents', 0)}\n"
        stats_text += f"Active Agents: {self.stats.get('active_agents', 0)}\n"
        stats_text += f"Total Requests: {self.stats.get('total_requests_processed', 0)}\n"
        self.stats_widget.update(stats_text)
        
        self.agents_table.clear()
        for agent in self.agents_data:
            self.agents_table.add_row(
                agent.get("agent_id", ""),
                agent.get("hostname", ""),
                str(len(agent.get("ipv6_addresses", []))),
                agent.get("status", ""),
                str(agent.get("requests_processed", 0)),
                agent.get("last_seen", "")
            )
        
        self.pool_table.clear()
        for ip in self.pool_status.get("ip_pool", []):
            self.pool_table.add_row(
                ip.get("ip", ""),
                ip.get("agent_id", ""),
                ip.get("status", ""),
                str(ip.get("requests_count", 0)),
                ip.get("last_used", "N/A") or "N/A"
            )
        
        self.history_table.clear()
        for item in self.history_data:
            metadata = item.get("metadata", {})
            result = item.get("result", {})
            self.history_table.add_row(
                metadata.get("timestamp", ""),
                metadata.get("agent_id", ""),
                metadata.get("source_ip", ""),
                "Success" if result.get("success") else "Failed",
                str(result.get("status_code", "N/A"))
            )
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-config":
            self.save_configuration()
        elif event.button.id == "load-config":
            self.load_configuration()
        elif event.button.id == "execute-btn":
            self.execute_request()
    
    @work
    async def save_configuration(self) -> None:
        try:
            config = {
                "url": self.url_input.value,
                "method": self.method_input.value,
                "headers": json.loads(self.headers_input.value or "{}"),
                "timeout": float(self.timeout_input.value or "30")
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.coordinator_url}/api/config/request",
                    json=config
                )
                
                if response.status_code == 200:
                    self.notify("Configuration saved successfully", severity="information")
                else:
                    self.notify(f"Failed to save configuration: {response.text}", severity="error")
        except Exception as e:
            self.notify(f"Error saving configuration: {e}", severity="error")
    
    @work
    async def load_configuration(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.coordinator_url}/api/config/request")
                
                if response.status_code == 200:
                    config = response.json()
                    self.url_input.value = config.get("url", "")
                    self.method_input.value = config.get("method", "GET")
                    self.headers_input.value = json.dumps(config.get("headers", {}))
                    self.timeout_input.value = str(config.get("timeout", 30))
                    self.notify("Configuration loaded", severity="information")
                else:
                    self.notify("No configuration available", severity="warning")
        except Exception as e:
            self.notify(f"Error loading configuration: {e}", severity="error")
    
    @work
    async def execute_request(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.coordinator_url}/api/execute")
                
                if response.status_code == 200:
                    result = response.json()
                    self.last_result = result
                    
                    result_text = f"Success!\n"
                    result_text += f"Agent: {result['metadata']['agent_id']}\n"
                    result_text += f"Source IP: {result['metadata']['source_ip']}\n"
                    result_text += f"Status Code: {result['result'].get('status_code', 'N/A')}\n"
                    
                    self.execute_result.update(result_text)
                    self.result_widget.update(json.dumps(result, indent=2))
                    
                    await self.refresh_data()
                else:
                    error_text = f"Failed: {response.text}"
                    self.execute_result.update(error_text)
        except Exception as e:
            self.execute_result.update(f"Error: {e}")
    
    def action_refresh(self) -> None:
        self.run_worker(self.refresh_data())
    
    def action_execute_request(self) -> None:
        self.run_worker(self.execute_request())
    
    def action_configure(self) -> None:
        self.query_one(TabbedContent).active = "config"