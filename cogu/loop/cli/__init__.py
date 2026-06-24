from cogu.loop.cli.goal import register_goal_parser
from cogu.loop.cli.loop_start import register_loop_start_parser
from cogu.loop.cli.loop_audit import register_loop_audit_parser
from cogu.loop.cli.loop_cost import register_loop_cost_parser

__all__ = [
    "register_goal_parser",
    "register_loop_start_parser",
    "register_loop_audit_parser",
    "register_loop_cost_parser",
]
