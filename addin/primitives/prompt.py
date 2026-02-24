"""
MCP Prompt Schema

This module defines the Prompt class for MCP transport arguments.
"""

import json
from typing import List, Optional


class Prompt:
    """
    MCP Prompt schema for defining prompt metadata.

    Provides a simple interface for creating and managing MCP prompt definitions
    that can be easily converted to JSON format.
    """

    def __init__(
        self,
        name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        arguments: Optional[List[dict]] = None
    ):
        """
        Initialize Prompt with required name and optional fields.

        Args:
            name: Unique identifier for the prompt
            title: Optional human-readable name for display
            description: Optional human-readable description
            arguments: Optional list of arguments for customization
        """
        self.name = name
        self.title = title
        self.description = description
        self.arguments = arguments or []

    def set_title(self, title: str) -> 'Prompt':
        """Set the prompt title. Returns self for method chaining."""
        self.title = title
        return self

    def set_description(self, description: str) -> 'Prompt':
        """Set the prompt description. Returns self for method chaining."""
        self.description = description
        return self

    def set_arguments(self, arguments: List[dict]) -> 'Prompt':
        """Set the arguments list. Returns self for method chaining."""
        self.arguments = arguments
        return self

    def add_argument(
        self,
        name: str,
        description: str,
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Add an argument to the prompt. Returns self for method chaining."""
        argument = {
            "name": name,
            "description": description,
            "required": required,
            **kwargs
        }
        self.arguments.append(argument)
        return self

    def add_string_argument(
        self,
        name: str,
        description: str,
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Add a string argument to the prompt. Returns self for method chaining."""
        return self.add_argument(
            name=name,
            description=description,
            required=required,
            type="string",
            **kwargs
        )

    def add_number_argument(
        self,
        name: str,
        description: str,
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Add a number argument to the prompt. Returns self for method chaining."""
        return self.add_argument(
            name=name,
            description=description,
            required=required,
            type="number",
            **kwargs
        )

    def add_boolean_argument(
        self,
        name: str,
        description: str,
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Add a boolean argument to the prompt. Returns self for method chaining."""
        return self.add_argument(
            name=name,
            description=description,
            required=required,
            type="boolean",
            **kwargs
        )

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {
            'name': self.name
        }

        if self.title:
            result['title'] = self.title
        if self.description:
            result['description'] = self.description
        if self.arguments:
            result['arguments'] = self.arguments

        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Prompt(name='{self.name}', title='{self.title}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"Prompt(name='{self.name}', title='{self.title}', "
                f"description='{self.description}')")

    @classmethod
    def create_simple(cls, name: str, description: str, **kwargs) -> 'Prompt':
        """Create a simple prompt with basic information."""
        return cls(name=name, description=description, **kwargs)

    @classmethod
    def create_with_string_arg(
        cls,
        name: str,
        description: str,
        arg_name: str = "input",
        arg_description: str = "Input parameter",
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Create a prompt that accepts a single string argument."""
        prompt = cls.create_simple(name, description, **kwargs)
        prompt.add_string_argument(arg_name, arg_description, required)
        return prompt

    @classmethod
    def create_with_number_arg(
        cls,
        name: str,
        description: str,
        arg_name: str = "value",
        arg_description: str = "Numeric parameter",
        required: bool = False,
        **kwargs
    ) -> 'Prompt':
        """Create a prompt that accepts a single number argument."""
        prompt = cls.create_simple(name, description, **kwargs)
        prompt.add_number_argument(arg_name, arg_description, required)
        return prompt
