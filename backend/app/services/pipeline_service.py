from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRun:
    """Tracks a single pipeline execution."""

    def __init__(self) -> None:
        self.status: PipelineStatus = PipelineStatus.IDLE
        self.process: Optional[subprocess.Popen] = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.log_lines: list[str] = []
        self.subscribers: list[WebSocket] = []
        self.params: dict = {}
        self.exit_code: Optional[int] = None
        self._reader_thread: Optional[threading.Thread] = None


class PipelineService:
    """Manages pipeline execution lifecycle: start, stop, status, log streaming.

    Runs `run_pipeline.py` as a subprocess using `subprocess.Popen`
    (not asyncio.create_subprocess_exec) for maximum Windows compatibility.
    A background thread reads stdout and pushes lines into an asyncio Queue,
    which an async task then broadcasts to WebSocket subscribers.
    """

    def __init__(self) -> None:
        self._run = PipelineRun()
        self._lock = asyncio.Lock()
        self._log_queue: asyncio.Queue[str] = asyncio.Queue()
        self._broadcast_task: Optional[asyncio.Task] = None

    @property
    def status(self) -> PipelineStatus:
        return self._run.status

    @property
    def params(self) -> dict:
        return self._run.params

    def get_status_detail(self) -> dict:
        """Return full pipeline status for API consumers."""
        return {
            "status": self._run.status.value,
            "started_at": self._run.started_at.isoformat() if self._run.started_at else None,
            "completed_at": self._run.completed_at.isoformat() if self._run.completed_at else None,
            "params": self._run.params,
            "exit_code": self._run.exit_code,
            "log_line_count": len(self._run.log_lines),
        }

    async def start(
        self,
        mode: str = "test",
        platforms: list[str] | None = None,
        login_type: str = "qrcode",
        headless: bool = False,
        schedule: str | None = None,
    ) -> dict:
        """Start the pipeline as a subprocess.

        Returns:
            Dict with success status and message.
        """
        async with self._lock:
            if self._run.status == PipelineStatus.RUNNING:
                return {"success": False, "error": "Pipeline is already running"}

            platforms = platforms or ["xhs"]
            platform_str = ",".join(platforms)

            # Build the command
            backend_dir = str(Path(__file__).resolve().parents[2])  # -> backend/
            python_exe = sys.executable
            script_path = os.path.join(backend_dir, "run_pipeline.py")

            cmd = [
                python_exe, script_path,
                "--mode", mode,
                "--platform", platform_str,
                "--login-type", login_type,
            ]
            if headless:
                cmd.append("--headless")
            if schedule and mode == "prod":
                cmd.extend(["--schedule", schedule])

            # Preserve existing WebSocket subscribers across PipelineRun reset.
            # Without this, start() creates a new PipelineRun with an empty
            # subscribers list, so already-connected WebSocket clients stop
            # receiving log messages until they manually reconnect.
            old_subscribers = self._run.subscribers

            self._run = PipelineRun()
            self._run.subscribers = old_subscribers
            self._run.status = PipelineStatus.RUNNING
            self._run.started_at = datetime.now()
            self._run.params = {
                "mode": mode,
                "platforms": platforms,
                "login_type": login_type,
                "headless": headless,
                "schedule": schedule,
            }

            logger.info(f"[PipelineService] Starting pipeline: {' '.join(cmd)}")

            try:
                self._run.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=backend_dir,
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                pid = self._run.process.pid

                # Start background thread to read stdout
                self._run._reader_thread = threading.Thread(
                    target=self._read_stdout_in_thread,
                    daemon=True,
                )
                self._run._reader_thread.start()

                # Start async broadcast task
                self._broadcast_task = asyncio.create_task(self._broadcast_loop())

            except Exception as e:
                self._run.status = PipelineStatus.FAILED
                self._run.completed_at = datetime.now()
                logger.error(f"[PipelineService] Failed to start pipeline: {e}")
                return {"success": False, "error": str(e)}

            return {"success": True, "message": "Pipeline started", "pid": pid}

    async def stop(self) -> dict:
        """Stop the running pipeline."""
        async with self._lock:
            if self._run.status != PipelineStatus.RUNNING:
                return {"success": False, "error": f"Pipeline is not running (status={self._run.status.value})"}

            if not self._run.process or self._run.process.poll() is not None:
                return {"success": False, "error": "No active process to stop"}

            self._run.status = PipelineStatus.STOPPING
            pid = self._run.process.pid

            if os.name == "nt":
                # Windows: kill the entire process tree
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception as e:
                    logger.warning(f"[PipelineService] taskkill failed for PID {pid}: {e}")
                    try:
                        self._run.process.kill()
                    except ProcessLookupError:
                        pass
            else:
                try:
                    self._run.process.terminate()
                    self._run.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    try:
                        self._run.process.kill()
                    except ProcessLookupError:
                        pass

            self._run.status = PipelineStatus.FAILED
            self._run.exit_code = -1
            self._run.completed_at = datetime.now()

            await self._broadcast(json.dumps({
                "type": "status",
                "status": "stopped",
                "message": "Pipeline stopped by user",
            }))

            return {"success": True, "message": "Pipeline stopped"}

    async def subscribe(self, websocket: WebSocket) -> None:
        """Subscribe a WebSocket client to log broadcasts."""
        await websocket.accept()
        self._run.subscribers.append(websocket)

        # Send existing logs to new subscriber
        for line in self._run.log_lines[-200:]:  # last 200 lines
            try:
                msg = json.dumps({"type": "log", "line": line})
                await websocket.send_text(msg)
            except Exception:
                break

        # Send current status
        try:
            await websocket.send_text(json.dumps({
                "type": "status",
                "status": self._run.status.value,
            }))
        except Exception:
            pass

    def unsubscribe(self, websocket: WebSocket) -> None:
        """Remove a WebSocket subscriber."""
        if websocket in self._run.subscribers:
            self._run.subscribers.remove(websocket)

    # ── Internal: Thread-based stdout reader ────────────────────

    def _read_stdout_in_thread(self) -> None:
        """Read subprocess stdout in a background thread (blocking I/O).

        This avoids the Windows asyncio event loop limitation where
        asyncio.create_subprocess_exec is not supported under SelectorEventLoop.
        Lines are pushed into an asyncio Queue for the async broadcast loop.
        """
        process = self._run.process
        if not process or not process.stdout:
            return

        try:
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                # Push to asyncio queue (thread-safe)
                self._log_queue.put_nowait(line)
        except Exception as e:
            logger.error(f"[PipelineService] Error reading pipeline output: {e}")
        finally:
            # Signal end of stream
            self._log_queue.put_nowait("__EOF__")

    async def _broadcast_loop(self) -> None:
        """Async loop that reads from the log queue and broadcasts to WebSocket clients."""
        try:
            while True:
                try:
                    # Use wait to avoid busy-polling
                    line = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check if process has exited
                    if self._run.process and self._run.process.poll() is not None:
                        break
                    continue

                if line == "__EOF__":
                    break

                self._run.log_lines.append(line)

                # Keep log buffer bounded (last 5000 lines)
                if len(self._run.log_lines) > 5000:
                    self._run.log_lines = self._run.log_lines[-3000:]

                # Broadcast to all subscribers
                msg = json.dumps({"type": "log", "line": line})
                await self._broadcast(msg)

        except asyncio.CancelledError:
            pass
        finally:
            # Finalize: get exit code
            exit_code = -1
            if self._run.process:
                exit_code = self._run.process.wait(timeout=10) if self._run.process.poll() is None else self._run.process.returncode
                exit_code = exit_code if exit_code is not None else -1

            self._run.exit_code = exit_code
            self._run.completed_at = datetime.now()

            if self._run.status == PipelineStatus.STOPPING:
                self._run.status = PipelineStatus.FAILED
            else:
                self._run.status = PipelineStatus.COMPLETED if exit_code == 0 else PipelineStatus.FAILED

            status_msg = json.dumps({
                "type": "status",
                "status": self._run.status.value,
                "exit_code": exit_code,
                "message": "Pipeline completed" if exit_code == 0 else "Pipeline failed",
            })
            await self._broadcast(status_msg)
            logger.info(f"[PipelineService] Pipeline exited with code {exit_code}")

    async def _broadcast(self, message: str) -> None:
        """Send a message to all connected WebSocket subscribers."""
        dead = []
        for ws in self._run.subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._run.subscribers.remove(ws)


# Singleton service instance
pipeline_service = PipelineService()
