from cogu.tools.builtin.file import register_file_tools
from cogu.tools.builtin.shell import register_shell_tools
from cogu.tools.builtin.web import register_web_tools
from cogu.tools.builtin.office import register_office_tools
from cogu.tools.builtin.browser import register_browser_tools
from cogu.tools.builtin.weather import register_weather_tools
from cogu.tools.builtin.stock import register_stock_tools
from cogu.tools.builtin.system import register_system_tools
from cogu.tools.builtin.gui import register_gui_tools
from cogu.tools.base import ToolRegistry


def register_builtin_tools(registry: ToolRegistry):
    register_file_tools(registry)
    register_shell_tools(registry)
    register_web_tools(registry)
    register_office_tools(registry)
    register_browser_tools(registry)
    register_weather_tools(registry)
    register_stock_tools(registry)
    register_system_tools(registry)
    register_gui_tools(registry)