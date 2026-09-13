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
