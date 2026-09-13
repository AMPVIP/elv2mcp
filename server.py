#!/usr/bin/env python3
"""
elv2mcp — Universal MCP Adapter for Extra Low Voltage Systems.

MVP: Hikvision (ISAPI) and Dahua (CGI API) read-only tools.
Write operations disabled unless ELV2MCP_ALLOW_WRITE=true.
"""

import os
import asyncio
from typing import Optional
from dataclasses import dataclass

import httpx
from fastmcp import FastMCP, Image
from fastmcp.exceptions import ToolError

# ─── Configuration ───────────────────────────────────────────────

@dataclass
class DeviceConfig:
    """Configuration for a single ELV device."""
    ip: str
    username: str
    password: str
    port: int = 80
    vendor: str = "hikvision"  # or "dahua"
    use_https: bool = False
    allow_write: bool = False

def load_devices_from_env() -> dict[str, DeviceConfig]:
    """
    Load device configs from environment variables.

    Format: ELV2MCP_DEVICES='{"cam1": {"ip": "192.168.1.100", "vendor": "hikvision", ...}}'
    Or individual env vars: ELV2MCP_DEVICE_CAM1_IP, etc.
    
    For MVP, we use a simple JSON env var to keep it flexible.
    """
    import json
    raw = os.environ.get("ELV2MCP_DEVICES", "{}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid ELV2MCP_DEVICES JSON: {e}")

    devices = {}
    for name, cfg in data.items():
        devices[name] = DeviceConfig(
            ip=cfg["ip"],
            username=cfg.get("username", os.environ.get("ELV2MCP_DEFAULT_USER", "")),
            password=cfg.get("password", os.environ.get("ELV2MCP_DEFAULT_PASS", "")),
            port=cfg.get("port", 80),
            vendor=cfg.get("vendor", "hikvision").lower(),
            use_https=cfg.get("use_https", False),
            allow_write=cfg.get("allow_write", False),
        )
    return devices

# ─── HTTP Client (shared) ────────────────────────────────────────

class AsyncHTTPClient:
    """Thin wrapper around httpx.AsyncClient with digest auth support."""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout, verify=False)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def get(self, url: str, username: str, password: str) -> httpx.Response:
        """GET with HTTP Digest authentication."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with'.")
        return await self._client.get(
            url,
            auth=httpx.DigestAuth(username, password),
        )

# ─── Hikvision ISAPI Provider ───────────────────────────────────

class HikvisionProvider:
    """
    Hikvision ISAPI implementation.
    Docs: ISAPI uses HTTP Digest auth, XML responses.
    Snapshots: /ISAPI/Streaming/channels/{id}/picture
    Device info: /ISAPI/System/deviceInfo
    Channels: /ISAPI/Streaming/channels
    """
    
    VENDOR = "hikvision"

    @staticmethod
    def _base_url(cfg: DeviceConfig) -> str:
        scheme = "https" if cfg.use_https else "http"
        return f"{scheme}://{cfg.ip}:{cfg.port}"

    @staticmethod
    async def get_device_info(cfg: DeviceConfig, client: AsyncHTTPClient) -> dict:
        """Fetch device model, serial, firmware via ISAPI."""
        url = f"{HikvisionProvider._base_url(cfg)}/ISAPI/System/deviceInfo"
        try:
            resp = await client.get(url, cfg.username, cfg.password)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ToolError(f"Hikvision deviceInfo failed: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ToolError(f"Hikvision unreachable: {e}")

        # Parse minimal XML (ISAPI returns XML)
        text = resp.text
        # Simple extraction — in production use xmltodict
        import re
        def extract(tag: str) -> str:
            m = re.search(rf"<{tag}>(.*?)</{tag}>", text)
            return m.group(1) if m else "unknown"

        return {
            "vendor": "Hikvision",
            "model": extract("model"),
            "serial": extract("serialNumber"),
            "firmware": extract("firmwareVersion"),
            "device_name": extract("deviceName"),
        }

    @staticmethod
    async def get_snapshot(cfg: DeviceConfig, client: AsyncHTTPClient, channel: int = 1) -> Image:
        """
        Fetch JPEG snapshot from Hikvision channel.
        Channel format: {camera}{stream} — 101 = camera 1 main stream [citation:2].
        """
        url = f"{HikvisionProvider._base_url(cfg)}/ISAPI/Streaming/channels/{channel}/picture"
        try:
            resp = await client.get(url, cfg.username, cfg.password)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ToolError(f"Hikvision snapshot failed for channel {channel}: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ToolError(f"Hikvision snapshot request error: {e}")

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            raise ToolError(f"Expected image, got {content_type}")

        return Image(data=resp.content, format="jpeg")

    @staticmethod
    async def list_channels(cfg: DeviceConfig, client: AsyncHTTPClient) -> list[dict]:
        """Enumerate available streaming channels."""
        url = f"{HikvisionProvider._base_url(cfg)}/ISAPI/Streaming/channels"
        try:
            resp = await client.get(url, cfg.username, cfg.password)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ToolError(f"Hikvision channels failed: HTTP {e.response.status_code}")

        text = resp.text
        # Extract channel IDs from XML
        import re
        channel_ids = re.findall(r"<id>(.*?)</id>", text)
        return [{"id": cid, "vendor": "Hikvision"} for cid in channel_ids]

# ─── Dahua CGI Provider ─────────────────────────────────────────

class DahuaProvider:
    """
    Dahua CGI API implementation.
    Snapshot: /cgi-bin/snapshot.cgi?channel={id} [citation:3]
    Device info: /cgi-bin/magicBox.cgi?action=getSystemInfo
    Digest auth required [citation:3].
    """
    
    VENDOR = "dahua"

    @staticmethod
    def _base_url(cfg: DeviceConfig) -> str:
        scheme = "https" if cfg.use_https else "http"
        return f"{scheme}://{cfg.ip}:{cfg.port}"

    @staticmethod
    async def get_device_info(cfg: DeviceConfig, client: AsyncHTTPClient) -> dict:
        """Fetch device info via magicBox CGI."""
        url = f"{DahuaProvider._base_url(cfg)}/cgi-bin/magicBox.cgi?action=getSystemInfo"
        try:
            resp = await client.get(url, cfg.username, cfg.password)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ToolError(f"Dahua deviceInfo failed: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ToolError(f"Dahua unreachable: {e}")

        # Dahua returns plain text: key=value lines
        lines = resp.text.strip().splitlines()
        info = {}
        for line in lines:
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()

        return {
            "vendor": "Dahua",
            "model": info.get("type", "unknown"),
            "serial": info.get("serialNumber", "unknown"),
            "firmware": info.get("softwareVersion", "unknown"),
        }

    @staticmethod
    async def get_snapshot(cfg: DeviceConfig, client: AsyncHTTPClient, channel: int = 1) -> Image:
        """Fetch JPEG snapshot from Dahua channel."""
        url = f"{DahuaProvider._base_url(cfg)}/cgi-bin/snapshot.cgi?channel={channel}"
        try:
            resp = await client.get(url, cfg.username, cfg.password)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ToolError(f"Dahua snapshot failed for channel {channel}: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ToolError(f"Dahua snapshot request error: {e}")

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            raise ToolError(f"Expected image, got {content_type}")

        return Image(data=resp.content, format="jpeg")

# ─── FastMCP Server ──────────────────────────────────────────────

mcp = FastMCP("elv2mcp")

# Load devices once at startup
_devices = load_devices_from_env()

def _get_device(name: str) -> DeviceConfig:
    """Resolve device by name or raise."""
    if name not in _devices:
        raise ToolError(
            f"Device '{name}' not found. Available: {list(_devices.keys()) or 'none configured'}"
        )
    return _devices[name]

# ─── Tools ───────────────────────────────────────────────────────

@mcp.tool
async def elv_list_devices() -> list[dict]:
    """
    List all configured ELV devices.
    Returns device names, IPs, vendors, and whether write is allowed.
    """
    return [
        {
            "name": name,
            "ip": cfg.ip,
            "vendor": cfg.vendor,
            "allow_write": cfg.allow_write,
        }
        for name, cfg in _devices.items()
    ]

@mcp.tool
async def elv_get_device_info(device_name: str) -> dict:
    """
    Get basic information about a camera or NVR (model, serial, firmware).
    
    Args:
        device_name: Name of the device from elv_list_devices.
    """
    cfg = _get_device(device_name)

    async with AsyncHTTPClient() as client:
        if cfg.vendor == "hikvision":
            return await HikvisionProvider.get_device_info(cfg, client)
        elif cfg.vendor == "dahua":
            return await DahuaProvider.get_device_info(cfg, client)
        else:
            raise ToolError(f"Unsupported vendor: {cfg.vendor}")

@mcp.tool
async def elv_get_snapshot(device_name: str, channel: int = 1) -> Image:
    """
    Capture a single JPEG snapshot from a specific camera channel.
    
    Args:
        device_name: Name of the device from elv_list_devices.
        channel: Channel number (1 for first camera). Default 1.
    """
    cfg = _get_device(device_name)

    async with AsyncHTTPClient() as client:
        if cfg.vendor == "hikvision":
            return await HikvisionProvider.get_snapshot(cfg, client, channel)
        elif cfg.vendor == "dahua":
            return await DahuaProvider.get_snapshot(cfg, client, channel)
        else:
            raise ToolError(f"Unsupported vendor: {cfg.vendor}")

@mcp.tool
async def elv_list_channels(device_name: str) -> list[dict]:
    """
    List all available video channels on a device.
    Note: Dahua CGI may not expose a full channel list; returns empty for now.
    
    Args:
        device_name: Name of the device from elv_list_devices.
    """
    cfg = _get_device(device_name)

    async with AsyncHTTPClient() as client:
        if cfg.vendor == "hikvision":
            return await HikvisionProvider.list_channels(cfg, client)
        elif cfg.vendor == "dahua":
            # Dahua doesn't have a straightforward channel list in basic CGI.
            # For MVP, return a hint.
            return [{"id": "1", "vendor": "Dahua", "note": "Channel list not implemented for Dahua MVP"}]
        else:
            raise ToolError(f"Unsupported vendor: {cfg.vendor}")

# ─── Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    # stdio transport for local MCP clients (Claude Desktop, Cursor, etc.)
    mcp.run(transport="stdio")
