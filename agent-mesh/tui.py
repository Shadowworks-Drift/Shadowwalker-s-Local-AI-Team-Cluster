"""
Agent Mesh TUI — Mission Control
─────────────────────────────────
Textual-based terminal dashboard.
Connects to FastAPI backend via WebSocket.
Each agent gets a live panel showing activity.
"""

import asyncio
import json
import sys
from datetime import datetime

from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Static, RichLog, Input, Button
from textual.reactive import reactive
from textual import work
from textual.css.query import NoMatches
from rich.text import Text

try:
    import websockets
except ImportError:
    print("Missing dependency: pip install websockets")
    sys.exit(1)


# ── Agent Panel Widget ────────────────────────────────────────────────────────

class AgentPanel(Static):
    """A single agent's status panel with live log."""

    status = reactive("idle")

    STATUS_ICONS = {
        "idle":     "⚫",
        "working":  "🔥",
        "complete": "✅",
        "error":    "❌",
    }

    STATUS_COLORS = {
        "idle":     "dim",
        "working":  "bold yellow",
        "complete": "bold green",
        "error":    "bold red",
    }

    def __init__(self, agent_name: str, role_desc: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self.role_desc = role_desc

    def compose(self):
        yield Static(id=f"header-{self.agent_name}", classes="agent-header")
        yield RichLog(id=f"log-{self.agent_name}", classes="agent-log", wrap=True, max_lines=20000)

    def on_mount(self):
        self._update_header()

    def watch_status(self, new_status: str):
        self._update_header()

    def _update_header(self):
        icon = self.STATUS_ICONS.get(self.status, "⚫")
        color = self.STATUS_COLORS.get(self.status, "dim")
        try:
            header = self.query_one(f"#header-{self.agent_name}", Static)
            styled = Text()
            styled.append(f" {icon} {self.agent_name.upper()}", style="bold")
            styled.append(f" — {self.role_desc} ", style="dim")
            styled.append(f"[{self.status}]", style=color)
            header.update(styled)
        except NoMatches:
            pass

    def add_log(self, message: str, style: str = ""):
        try:
            log_widget = self.query_one(f"#log-{self.agent_name}", RichLog)
            timestamp = datetime.now().strftime("%H:%M:%S")
            line = Text()
            line.append(f"{timestamp} ", style="dim")
            if style:
                line.append(message, style=style)
            else:
                line.append(message)
            log_widget.write(line)
        except NoMatches:
            pass


# ── System Log Widget ─────────────────────────────────────────────────────────

class SystemLog(Static):

    def compose(self):
        yield Static(id="system-header-text", classes="system-header")
        yield RichLog(id="system-log", classes="system-log-content", wrap=True, max_lines=500)

    def on_mount(self):
        try:
            header = self.query_one("#system-header-text", Static)
            header.update(Text(" 🌑 SYSTEM LOG", style="bold"))
        except NoMatches:
            pass

    def add_log(self, message: str, style: str = ""):
        try:
            log_widget = self.query_one("#system-log", RichLog)
            timestamp = datetime.now().strftime("%H:%M:%S")
            line = Text()
            line.append(f"{timestamp} ", style="dim")
            if style:
                line.append(message, style=style)
            else:
                line.append(message)
            log_widget.write(line)
        except NoMatches:
            pass


# ── Job Status Bar ────────────────────────────────────────────────────────────

class JobStatusBar(Static):

    def compose(self):
        yield Static(id="job-status-text")

    def on_mount(self):
        try:
            w = self.query_one("#job-status-text", Static)
            w.update(Text("🌑 NO ACTIVE JOB — Enter an objective below to start", style="dim"))
        except NoMatches:
            pass

    def update_job(self, objective: str = "", status: str = "", revision: int = 0, verdict: str = ""):
        try:
            w = self.query_one("#job-status-text", Static)
            if not objective:
                w.update(Text("🌑 NO ACTIVE JOB — Enter an objective below to start", style="dim"))
            else:
                styled = Text()
                styled.append("📋 ", style="bold")
                styled.append(objective[:80], style="bold white")
                if status:
                    styled.append(f" │ {status}", style="cyan")
                if revision > 0:
                    styled.append(f" │ Rev: {revision}", style="yellow")
                if verdict:
                    v_style = "bold green" if verdict == "PASS" else "bold red"
                    styled.append(f" │ {verdict}", style=v_style)
                w.update(styled)
        except NoMatches:
            pass


# ── Main TUI App ──────────────────────────────────────────────────────────────

class MeshDashboard(App):

    TITLE = "🌑 Agent Mesh — Mission Control"
    SUB_TITLE = "Phase 5 TUI"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 3 1fr 1fr 3;
    }

    .job-bar {
        height: 3;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }

    .agent-row {
        height: 1fr;
        layout: horizontal;
    }

    AgentPanel {
        width: 1fr;
        border: solid $secondary;
        margin: 0 1;
    }

    .agent-header {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }

    .agent-log {
        height: 1fr;
        padding: 0 1;
    }

    .system-row {
        height: 1fr;
        border: solid $accent;
        margin: 0 1;
    }

    .system-header {
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    .system-log-content {
        height: 1fr;
        padding: 0 1;
    }

    .input-row {
        height: 3;
        layout: horizontal;
        padding: 0 1;
    }

    #objective-input {
        width: 4fr;
    }

    #submit-btn {
        width: 1fr;
        min-width: 16;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reset", "Reset"),
        ("ctrl+l", "clear_logs", "Clear Logs"),
    ]

    def __init__(self, server_url: str = "ws://localhost:8000/ws", **kwargs):
        super().__init__(**kwargs)
        self.server_url = server_url
        self.connected = False
        self._agent_panels: dict[str, AgentPanel] = {}

    def compose(self):
        yield Header()
        yield JobStatusBar(classes="job-bar")

        architect_panel = AgentPanel("architect", "Planner — reasoning-fast", id="panel-architect")
        coder_panel = AgentPanel("coder", "Builder — coder-fast", id="panel-coder")
        critic_panel = AgentPanel("critic", "Reviewer — coder-fast", id="panel-critic")

        self._agent_panels = {
            "architect": architect_panel,
            "coder": coder_panel,
            "critic": critic_panel,
        }

        yield Horizontal(architect_panel, coder_panel, critic_panel, classes="agent-row")
        yield SystemLog(classes="system-row")
        yield Horizontal(
            Input(placeholder="Enter objective...", id="objective-input"),
            Button("▶ RUN", id="submit-btn", variant="success"),
            classes="input-row",
        )
        yield Footer()

    def on_mount(self):
        self.connect_ws()

    @work(exclusive=True, thread=False)
    async def connect_ws(self):
        system_log = self.query_one(SystemLog)
        system_log.add_log("Connecting to mesh backend...", "bold cyan")

        retry_count = 0
        max_retries = 5

        while retry_count < max_retries:
            try:
                async with websockets.connect(self.server_url) as ws:
                    self.connected = True
                    retry_count = 0
                    system_log.add_log("Connected to mesh backend ✓", "bold green")

                    async for message in ws:
                        try:
                            event = json.loads(message)
                            self.handle_event(event)
                        except json.JSONDecodeError:
                            system_log.add_log(f"Bad message: {message[:100]}", "red")

            except (ConnectionRefusedError, OSError) as e:
                retry_count += 1
                self.connected = False
                system_log.add_log(
                    f"Connection failed ({retry_count}/{max_retries}): {e}", "bold red")
                if retry_count < max_retries:
                    await asyncio.sleep(2)
            except Exception as e:
                self.connected = False
                system_log.add_log(f"WebSocket error: {e}", "bold red")
                await asyncio.sleep(2)
                retry_count += 1

        if not self.connected:
            system_log.add_log("Could not connect. Is server.py running?", "bold red")

    def handle_event(self, event: dict):
        event_type = event.get("type", "")
        agent = event.get("agent", "system")
        message = event.get("message", "")
        data = event.get("data", {})

        system_log = self.query_one(SystemLog)

        # ── Snapshot ──
        if event_type == "snapshot":
            for name, status in data.get("agent_states", {}).items():
                if name in self._agent_panels:
                    self._agent_panels[name].status = status
            job = data.get("job")
            if job:
                self.query_one(JobStatusBar).update_job(
                    objective=job.get("objective", ""),
                    status=job.get("status", ""),
                    revision=job.get("revision_count", 0),
                    verdict=job.get("verdict", ""),
                )
            recent = data.get("recent_events", [])
            if recent:
                system_log.add_log(f"Loaded {len(recent)} recent events", "dim")
            return

        # ── Agent status ──
        if event_type == "agent_status":
            if agent in self._agent_panels:
                self._agent_panels[agent].status = data.get("status", "idle")
            return

        # ── Phase events → agent panel + system log ──
        if event_type in ("phase_start", "phase_complete", "verdict"):
            if agent in self._agent_panels:
                panel = self._agent_panels[agent]

                style = ""
                if event_type == "phase_start":
                    style = "bold cyan"
                elif event_type == "phase_complete":
                    style = "bold green"
                elif event_type == "verdict":
                    style = "bold green" if data.get("verdict") == "PASS" else "bold red"

                panel.add_log(message, style)

                # Show content preview in agent panel
                if event_type == "phase_complete":
                    preview = (data.get("plan_preview") or
                               data.get("code_preview") or
                               data.get("review_preview") or "")
                    if preview:
                        panel.add_log("─" * 40, "dim")
                        for line in preview.split('\n')[:12]:
                            if line.strip():
                                panel.add_log(line.strip())
                        if len(preview.split('\n')) > 12:
                            panel.add_log("... (truncated)", "dim")
                        panel.add_log("─" * 40, "dim")

            # System log mirror
            sys_style = "bold yellow" if event_type == "verdict" else ("green" if event_type == "phase_complete" else "")
            system_log.add_log(f"[{agent}] {message}", sys_style)
            return

        # ── Routing ──
        if event_type == "routing":
            system_log.add_log(message, "bold cyan")
            return

        # ── Job lifecycle ──
        if event_type == "job_start":
            obj = message.split(": ", 1)[-1] if ": " in message else message
            self.query_one(JobStatusBar).update_job(objective=obj, status="running")
            system_log.add_log(f"🚀 {message}", "bold green")

        elif event_type == "job_complete":
            self.query_one(JobStatusBar).update_job(status="complete", verdict=data.get("verdict", ""))
            system_log.add_log(f"🌑 {message}", "bold green")

        elif event_type == "error":
            system_log.add_log(f"💥 {message}", "bold red")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "submit-btn":
            await self._submit_job()

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "objective-input":
            await self._submit_job()

    async def _submit_job(self):
        input_widget = self.query_one("#objective-input", Input)
        objective = input_widget.value.strip()
        if not objective:
            return

        system_log = self.query_one(SystemLog)
        if not self.connected:
            system_log.add_log("Not connected to backend!", "bold red")
            return

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/run",
                    json={"objective": objective, "max_revisions": 3},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    system_log.add_log(f"Job submitted: {objective}", "bold green")
                    input_widget.value = ""
                elif response.status_code == 409:
                    system_log.add_log("A job is already running", "bold yellow")
                else:
                    system_log.add_log(f"Submit error: {response.json()}", "bold red")
        except Exception as e:
            system_log.add_log(f"Failed to submit: {e}", "bold red")

    def action_reset(self):
        import httpx
        try:
            httpx.post("http://localhost:8000/reset", timeout=3.0)
        except Exception:
            pass
        for panel in self._agent_panels.values():
            panel.status = "idle"
        self.query_one(SystemLog).add_log("State reset", "bold cyan")
        self.query_one(JobStatusBar).update_job()

    def action_clear_logs(self):
        for panel in self._agent_panels.values():
            try:
                panel.query_one(f"#log-{panel.agent_name}", RichLog).clear()
            except NoMatches:
                pass
        try:
            self.query_one("#system-log", RichLog).clear()
        except NoMatches:
            pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent Mesh TUI Dashboard")
    parser.add_argument("--server", default="ws://localhost:8000/ws", help="WebSocket server URL")
    args = parser.parse_args()
    MeshDashboard(server_url=args.server).run()
