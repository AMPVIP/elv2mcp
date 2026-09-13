# elv2mcp

> Universal MCP adapter for Extra Low Voltage (ELV) systems — connect Hikvision, Dahua, and other security devices to AI agents via the Model Context Protocol.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

---

## 🎯 What is elv2mcp?

`elv2mcp` is a **Model Context Protocol (MCP) server** that bridges the gap between AI agents (Claude, GPT, Cursor, etc.) and physical security systems.

Today, thousands of ELV systems — cameras, NVRs, access control, alarms — sit isolated from modern AI workflows. They speak proprietary protocols (ISAPI, CGI, SDK) that LLMs cannot understand. `elv2mcp` translates these into **typed, safe, auditable MCP tools** that any AI agent can call.

**Think of it as a "USB-C for physical security"** — one adapter, many vendors, safe by default.

---

## ✨ Features

- **Multi-vendor support** — Hikvision (ISAPI), Dahua (CGI API), with a pluggable architecture for adding more (Bosch, Bolid, Axis, etc.)
- **Read-only by default** — snapshots, device info, and channel lists work out of the box. Write operations (PTZ, reboot) require explicit opt-in.
- **Typed tools** — AI agents call `elv_get_snapshot(device_name, channel)` instead of guessing raw HTTP requests.
- **Digest authentication** — native support for Hikvision and Dahua auth schemes.
- **Secure credentials** — never hardcoded. Loaded from environment variables or a `.env` file.
- **FastMCP-powered** — built on [FastMCP](https://github.com/jlowin/fastmcp), with automatic schema validation and stdio transport.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install fastmcp httpx
```

Or clone and install locally:

```bash
git clone https://github.com/AMPVIP/elv2mcp.git
cd elv2mcp
pip install -e .
```

### 2. Configure your devices

Set the `ELV2MCP_DEVICES` environment variable with a JSON map:

```bash
export ELV2MCP_DEVICES='{
  "cam1": {
    "ip": "192.168.1.100",
    "username": "admin",
    "password": "yourpass",
    "vendor": "hikvision",
    "port": 80
  },
  "cam2": {
    "ip": "192.168.1.101",
    "username": "admin",
    "password": "yourpass",
    "vendor": "dahua"
  }
}'
```

### 3. Run the server

```bash
python server.py
```

The server runs on **stdio** and waits for MCP client connections.

---

## 🔌 Connect to Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "elv2mcp": {
      "command": "/path/to/python",
      "args": ["/path/to/elv2mcp/server.py"],
      "env": {
        "ELV2MCP_DEVICES": "{\"cam1\": {\"ip\": \"192.168.1.100\", \"username\": \"admin\", \"password\": \"yourpass\", \"vendor\": \"hikvision\"}}"
      }
    }
  }
}
```

Restart Claude Desktop — the `elv_*` tools will appear in the interface.

---

## 🛠️ Available Tools

| Tool | Description | Hikvision | Dahua |
|------|-------------|-----------|-------|
| `elv_list_devices` | List all configured devices | ✅ | ✅ |
| `elv_get_device_info` | Get model, serial, firmware | ✅ | ✅ |
| `elv_get_snapshot` | Capture JPEG from a channel | ✅ | ✅ |
| `elv_list_channels` | Enumerate video channels | ✅ | ⚠️ MVP stub |

### Example prompts for AI agents

Once connected, you can ask Claude:

- *"List all my cameras and tell me which ones are online."*
- *"Take a snapshot from cam1 and describe what you see."*
- *"What firmware version is running on cam2?"*

---

## 🔐 Security

`elv2mcp` is designed with a **paranoid-by-default** philosophy:

- **Read-only by default** — all write operations (PTZ, reboot, config changes) are disabled unless `allow_write: true` is set per device.
- **No hardcoded credentials** — use environment variables or a `.env` file (never commit it).
- **Digest auth** — supports the auth schemes used by Hikvision and Dahua.
- **Audit-ready** — every tool call can be logged (coming soon).
- **Network isolation** — the server only talks to devices you explicitly configure.

> ⚠️ **Never expose this server to the public internet.** Run it on a trusted LAN or VPN.

---

## 🧩 Architecture

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   AI Agent      │◄─────►│   elv2mcp       │◄─────►│  Hikvision      │
│ (Claude, GPT)   │  MCP  │   FastMCP       │ HTTP  │  Dahua          │
└─────────────────┘       └─────────────────┘       └─────────────────┘
                                  │
                                  ├── HikvisionProvider (ISAPI)
                                  ├── DahuaProvider (CGI API)
                                  └── [Future: Bosch, Bolid, Axis]
```

The provider pattern makes it trivial to add new vendors — implement `get_device_info`, `get_snapshot`, and `list_channels` for the new protocol.

---

## 🗺️ Roadmap

- [x] Hikvision ISAPI support (device info, snapshot, channels)
- [x] Dahua CGI API support (device info, snapshot)
- [ ] PTZ control (Hikvision + Dahua) — behind `allow_write` flag
- [ ] Event stream / motion detection (Hikvision `alertStream`)
- [ ] Bosch BVMS provider
- [ ] Bolid provider
- [ ] Mock server for testing without real hardware
- [ ] Audit logging (JSON lines)
- [ ] MCP Registry publication

---

## 🤝 Contributing

Contributions are welcome — especially new vendor providers. To add a vendor:

1. Create `providers/your_vendor.py` with a class implementing `get_device_info`, `get_snapshot`, `list_channels`.
2. Register it in `server.py`'s dispatch logic.
3. Add tests and documentation.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🔗 Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io/) — the standard this project implements
- [FastMCP](https://github.com/jlowin/fastmcp) — Python framework for building MCP servers
- [legacy2mcp](https://github.com/legacy2mcp) — MCP adapter for SOAP/WSDL systems
- [plctap](https://github.com/plctap) — MCP adapter for industrial PLCs

---

## 👤 Author

**Andrey Pavlushov** — Low Current Engineer with 20+ years of experience in ELV systems, networking, and security.

- GitHub: [@AMPVIP](https://github.com/AMPVIP)
- Portfolio: [ampvip.github.io](https://ampvip.github.io)

---

*Built with the belief that the physical world deserves first-class AI tooling.*
