from urllib.request import urlopen, quote

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _weather_current(location: str, units: str = "m") -> str:
    try:
        url = f"https://wttr.in/{quote(location)}?format=%l:+%c+%t+%h+%w&{units}"
        with urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"Weather error: {e}"


def _weather_forecast(location: str, days: int = 3) -> str:
    try:
        url = f"https://wttr.in/{quote(location)}?{days}&T"
        with urlopen(url, timeout=10) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            lines = text.split("\n")
            cleaned = [l.rstrip() for l in lines if l.strip()]
            return "\n".join(cleaned[:60])
    except Exception as e:
        return f"Weather error: {e}"


def register_weather_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_weather_current, name="weather_current", description="Get current weather for a location (city name, airport code). No API key needed. Units: m=metric, u=US.").with_capability(ToolCapability.NETWORK).mark_concurrency_safe().with_group("weather"))
    registry.register(FunctionTool(_weather_forecast, name="weather_forecast", description="Get weather forecast for a location. Days: 1-3.").with_capability(ToolCapability.NETWORK).mark_concurrency_safe().with_group("weather"))
