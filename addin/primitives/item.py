"""
MCP Item Wrapper

This module defines the Item class for bundling MCP primitives with their handlers.
"""

from typing import Union, Any
from .tool import Tool
from .resource import Resource
from .prompt import Prompt


class Item:
    """
    MCP Item wrapper that contains a primitive and its handler function.

    Provides a simple interface for bundling MCP primitives (Tool, Resource, Prompt)
    with their corresponding handler functions.
    """

    def __init__(
        self,
        primitive: Union[Tool, Resource, Prompt],
        handler: callable,
        run_on_main_thread: bool = True
    ):
        """
        Initialize Item with a primitive and handler function.

        Args:
            primitive: A Tool, Resource, or Prompt instance
            handler: Function that takes the arguments as defined in the primitve's properties
            run_on_main_thread: If True, handler runs on main thread; else on worker thread
        """
        if not isinstance(primitive, (Tool, Resource, Prompt)):
            raise ValueError("Primitive must be a Tool, Resource, or Prompt instance")

        if not callable(handler):
            raise ValueError("Handler must be a callable function")

        self.name = primitive.name
        self.primitive = primitive
        self.handler = handler
        self.run_on_main_thread = run_on_main_thread

    def get_name(self) -> str:
        """Get the name of the primitive."""
        return self.primitive.name

    def get_type(self) -> str:
        """Get the type of the primitive."""
        if isinstance(self.primitive, Tool):
            return "tool"
        elif isinstance(self.primitive, Resource):
            return "resource"
        elif isinstance(self.primitive, Prompt):
            return "prompt"
        else:
            return "unknown"

    def to_dict(self) -> dict:
        """Convert the primitive to dictionary."""
        return self.primitive.to_dict()

    def to_json(self) -> str:
        """Convert the primitive to JSON string."""
        return self.primitive.to_json()

    def call_handler(self, kwargs: dict) -> Any:
        """
        Call the handler function with the provided arguments.

        Args:
            arguments: JSON string containing the arguments

        Returns:
            Result from the handler function
        """
        return self.handler(**kwargs)

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Item(type='{self.get_type()}', name='{self.get_name()}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Item(primitive={self.primitive}, handler={self.handler})"

    @classmethod
    def create_tool_item(
        cls,
        tool: Tool,
        handler: callable
    ) -> 'Item':
        """Create an Item with a Tool primitive."""
        return cls(primitive=tool, handler=handler)

    @classmethod
    def create_resource_item(
        cls,
        resource: Resource,
        handler: callable
    ) -> 'Item':
        """Create an Item with a Resource primitive."""
        return cls(primitive=resource, handler=handler)

    @classmethod
    def create_prompt_item(
        cls,
        prompt: Prompt,
        handler: callable
    ) -> 'Item':
        """Create an Item with a Prompt primitive."""
        return cls(primitive=prompt, handler=handler)
