import asyncio
import os
import tempfile
from pathlib import Path

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


async def _browser_navigate(url: str, wait_seconds: int = 3) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "-y", "@playwright/mcp@latest", "--url", url, "--wait", str(wait_seconds),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return stdout.decode("utf-8", errors="replace") or stderr.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return "Error: browser navigation timed out"
    except FileNotFoundError:
        return "Error: npx not found. Install Node.js from https://nodejs.org"
    except Exception as e:
        return f"Error: {e}"


async def _browser_screenshot(url: str, output: str = "", full_page: bool = True) -> str:
    out_path = Path(output) if output else Path(tempfile.gettempdir()) / "screenshot.png"
    try:
        args = ["npx", "-y", "@playwright/mcp@latest", "screenshot", url, "--output", str(out_path)]
        if full_page:
            args.append("--full-page")
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if out_path.exists():
            return f"Screenshot saved: {out_path} ({out_path.stat().st_size} bytes)"
        return f"Error taking screenshot: {stderr.decode('utf-8', errors='replace')}"
    except asyncio.TimeoutError:
        return "Error: screenshot timed out"
    except FileNotFoundError:
        return "Error: npx not found. Install Node.js from https://nodejs.org"
    except Exception as e:
        return f"Error: {e}"


async def _browser_extract(url: str, selector: str = "body") -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "-y", "@playwright/mcp@latest", "extract", url, "--selector", selector,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        result = stdout.decode("utf-8", errors="replace")
        if not result.strip():
            result = stderr.decode("utf-8", errors="replace")
        return result[:8000]
    except asyncio.TimeoutError:
        return "Error: extraction timed out"
    except FileNotFoundError:
        return "Error: npx not found. Install Node.js from https://nodejs.org"
    except Exception as e:
        return f"Error: {e}"


def register_browser_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_browser_navigate, name="browser_navigate", description="Navigate to a URL using Playwright browser. Returns page content.").with_capability(ToolCapability.NETWORK).with_group("browser"))
    registry.register(FunctionTool(_browser_screenshot, name="browser_screenshot", description="Take a screenshot of a web page using Playwright.").with_capability(ToolCapability.NETWORK).with_group("browser"))
    registry.register(FunctionTool(_browser_extract, name="browser_extract", description="Extract text content from a web page element using CSS selector.").with_capability(ToolCapability.NETWORK).mark_concurrency_safe().with_group("browser"))
