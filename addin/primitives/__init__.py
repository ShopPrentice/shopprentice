"""
ShopPrentice Primitives package

MCP protocol schema classes and registry.
"""

# Import schema classes
from .annotations import Annotations
from .tool import Tool
from .resource import Resource
from .prompt import Prompt
from .item import Item
from .registry import (
    Registry,
    get_registry,
    reset_registry,
    register,
    get_tool,
    get_resource,
    get_prompt,
    has_tool,
    has_resource,
    has_prompt,
    get_tools,
    get_resources,
    get_prompts,
    clear_registry,
    registry_count
)

__all__ = [
    'Annotations',
    'Tool',
    'Resource',
    'Prompt',
    'Item',
    'Registry',
    'get_registry',
    'reset_registry',
    'register',
    'get_tool',
    'get_resource',
    'get_prompt',
    'has_tool',
    'has_resource',
    'has_prompt',
    'get_tools',
    'get_resources',
    'get_prompts',
    'clear_registry',
    'registry_count',
]
