import asyncio
import logging
import socket
import threading
from datetime import datetime, timezone
from typing import Protocol, cast, List, Dict, Any

from fastmcp import FastMCP, Context
from pydantic import AnyUrl, TypeAdapter
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from device import Device, WindowHandle

logger = logging.getLogger(__name__)


class MDNS:
    def __init__(self) -> None:
        self.registered: Dict[str, ServiceInfo] = {}
        self.zc = Zeroconf(ip_version=IPVersion.V4Only)
        self.service_type = "_mcp._tcp.local."
        self.hostname = socket.gethostname()
        self.local_ip = self._resolve_local_ip()

    @staticmethod
    def _resolve_local_ip() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            logger.warning("mDNS: Could not determine local IP, falling back to localhost.")
            return "127.0.0.1"
        finally:
            s.close()

    def register_mdns(self, name: str, port: int) -> None:
        try:
            service_name = f"{name}.{self.service_type}"
            service_info = ServiceInfo(
                type_=self.service_type,
                name=service_name,
                addresses=[socket.inet_aton(self.local_ip)],
                port=port,
                properties={
                    "version": "1.0",
                    "path": "/sse",
                    "server_type": "fastmcp"
                },
                server=f"{self.hostname}.local.",
            )

            logger.info(f"mDNS: Registering {service_name} at {self.local_ip}:{port}")
            self.zc.register_service(service_info)
            self.registered[name] = service_info
        except Exception as e:
            logger.error(f"mDNS Registration failed: {e}")

    def unregister_mdns(self, name: str) -> None:
        service_info = self.registered.pop(name, None)
        if service_info is not None:
            logger.info(f"mDNS: Unregistering service {name}...")
            self.zc.unregister_service(service_info)

    def close(self) -> None:
        """Properly close all registrations and tear down Zeroconf."""
        for name in list(self.registered):
            self.unregister_mdns(name)
        self.zc.close()


class ResourceUpdateSession(Protocol):
    async def send_resource_updated(self, uri: AnyUrl) -> None:
        ...


class EnoceanMCPServer:
    # Extracted to avoid re-instantiating in high-frequency notification loops
    _url_adapter = TypeAdapter(AnyUrl)

    def __init__(self, name: str, port: int, devices: List[WindowHandle], host: str = "0.0.0.0") -> None:
        self.name = name
        self.host = host
        self.port = port

        self.mdns = MDNS()
        self.mcp = FastMCP(self.name)
        self.active_sessions: set[ResourceUpdateSession] = set()
        self.devices = devices
        self.loop = asyncio.new_event_loop()
        self.last_state: Dict[str, bool] = {}

        # Proper iteration (avoiding side-effect list comprehensions)
        for device in self.devices:
            device.register_listener(self.__on_value_changed)

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.mcp.resource("handle://window")
        def get_window_handle_names() -> List[str]:
            """
            Discover all available EnOcean window handles tracked by the server.
            Returns a list of device names. Use these names to query specific states.
            """
            return [d.name for d in self.devices]

        @self.mcp.resource("handle://window/{name}")
        def get_window_handle(name: str, ctx: Context) -> Dict[str, Any]:
            """
            Retrieve the current status (OPEN or CLOSED) of a specific window handle.
            Accessing this resource automatically subscribes the client to SSE push notifications.
            """
            try:
                req_ctx = ctx.request_context
                if req_ctx and req_ctx.session and req_ctx.session not in self.active_sessions:
                    self.active_sessions.add(cast(ResourceUpdateSession, req_ctx.session))
                    logger.info(f"[Server] Client session registered for updates (Resource: {name}).")
            except Exception as e:
                logger.debug(f"[Server] Could not register session: {e}")

            for d in self.devices:
                if d.name == name:
                    return {
                        "name": d.name,
                        "state": "CLOSED" if d.closed else "OPEN"
                    }

            # Let FastMCP handle the HTTP Error natively rather than returning strings
            raise ValueError(f"Device '{name}' not found.")


        @self.mcp.tool(name="device_overview")
        def get_device_overview() -> Dict[str, Any]:
            """
            Retrieve a real-time overview of all window handles.
            Returns a dictionary mapping device names to their status and last update time.
            OPEN windows are sorted to appear first.
            """
            if not self.devices:
                return {"error": "No devices are currently available."}

            # Extract only the window handles from the devices list
            window_handles = [device for device in self.devices if isinstance(device, WindowHandle)]

            if not window_handles:
                return {"error": "No window handles are currently available among the devices."}

            overview = {}
            # Sort so OPEN windows (closed == False) appear first
            sorted_window_handles = sorted(window_handles, key=lambda x: x.closed)

            for window_handle in sorted_window_handles:
                status = "CLOSED" if window_handle.closed else "OPEN"
                timestamp = None

                if window_handle.last_state_update:
                    ts_aware = (
                        window_handle.last_state_update
                        if window_handle.last_state_update.tzinfo
                        else window_handle.last_state_update.replace(tzinfo=timezone.utc)
                    )
                    timestamp = ts_aware.strftime("%Y-%m-%dT%H:%M:%S%z")

                overview[window_handle.name] = {
                    "state": status,
                    "last_update": timestamp
                }

            return {"windows": overview}


    def __on_value_changed(self, device: Device) -> None:
        if not self.loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._trigger_client_notification(device.name), self.loop)

    async def _trigger_client_notification(self, name: str) -> None:
        if not self.active_sessions:
            return

        for device in self.devices:
            if device.name == name:
                last_state = self.last_state.get(name, None)
                if device.closed != last_state:
                    self.last_state[name] = device.closed
                    dead_sessions = set()

                    uri = self._url_adapter.validate_python(f"handle://window/{name}")
                    for session in self.active_sessions:
                        try:
                            await session.send_resource_updated(uri)
                        except Exception:
                            dead_sessions.add(session)

                    self.active_sessions.difference_update(dead_sessions)
                break

    async def __run(self) -> None:
        logger.info(f"MCP Server '{self.name}' running on http://{self.host}:{self.port}/sse")
        await self.mcp.run_async(
            transport="sse",
            host=self.host,
            port=self.port,
            uvicorn_config={"access_log": False, "log_config": None}
        )

    def start(self) -> None:
        self.mdns.register_mdns(self.name, self.port)

        def _run_loop() -> None:
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self.__run())
            finally:
                self.loop.close()

        thread = threading.Thread(target=_run_loop, daemon=True)
        thread.start()

    def stop(self) -> None:
        self.mdns.close()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        logger.info("MCP Server stopped")