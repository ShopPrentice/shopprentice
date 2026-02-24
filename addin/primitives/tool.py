"""
MCP Tool Schema

This module defines the Tool class for MCP transport arguments.
"""

import json
from typing import Optional, Any
from .annotations import Annotations


class Tool:
    """
    MCP Tool schema for defining tool metadata and behavior.

    Provides a simple interface for creating and managing MCP tool definitions
    that can be easily converted to JSON format.
    """

    def __init__(
        self,
        name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[dict] = None,
        output_schema: Optional[dict] = None,
        annotations: Optional[Annotations] = None,
        additional_properties: Optional[bool] = None
    ):
        """
        Initialize Tool with required name and optional fields.

        Args:
            name: Unique identifier for the tool
            title: Optional human-readable name for display
            description: Human-readable description of functionality
            input_schema: JSON Schema defining expected parameters
            output_schema: Optional JSON Schema defining expected output structure
            annotations: Optional properties describing tool behavior
            additional_properties: Whether additional properties are allowed in input schema
        """
        self.name = name
        self.title = title
        self.description = description
        self.input_schema = input_schema or {}
        self.output_schema = output_schema
        self.annotations = annotations
        self.additional_properties = additional_properties

    def set_title(self, title: str) -> 'Tool':
        """Set the tool title. Returns self for method chaining."""
        self.title = title
        return self

    def set_description(self, description: str) -> 'Tool':
        """Set the tool description. Returns self for method chaining."""
        self.description = description
        return self

    def set_input_schema(self, schema: dict) -> 'Tool':
        """Set the input JSON schema. Returns self for method chaining."""
        self.input_schema = schema
        return self

    def set_output_schema(self, schema: dict) -> 'Tool':
        """Set the output JSON schema. Returns self for method chaining."""
        self.output_schema = schema
        return self

    def set_annotations(self, annotations: Annotations) -> 'Tool':
        """Set the tool annotations. Returns self for method chaining."""
        self.annotations = annotations
        return self

    def set_additional_properties(self, additional_properties: bool) -> 'Tool':
        """Set whether additional properties are allowed. Returns self for method chaining."""
        self.additional_properties = additional_properties
        return self

    def strict_schema(self) -> 'Tool':
        """Set additionalProperties to False for strict schema validation. Returns self for method chaining."""
        self.additional_properties = False
        return self

    def flexible_schema(self) -> 'Tool':
        """Set additionalProperties to True for flexible schema validation. Returns self for method chaining."""
        self.additional_properties = True
        return self

    def add_input_property(self, name: str, property_schema: dict) -> 'Tool':
        """Add a property to the input schema. Returns self for method chaining."""
        if 'properties' not in self.input_schema:
            self.input_schema['properties'] = {}
        self.input_schema['properties'][name] = property_schema
        return self

    def add_required_input(self, property_name: str) -> 'Tool':
        """Add a property to the required list. Returns self for method chaining."""
        if 'required' not in self.input_schema:
            self.input_schema['required'] = []
        if property_name not in self.input_schema['required']:
            self.input_schema['required'].append(property_name)
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {
            'name': self.name
        }

        if self.title:
            result['title'] = self.title
        if self.description:
            result['description'] = self.description
        if self.input_schema:
            # Create a copy of input_schema to avoid modifying the original
            input_schema = self.input_schema.copy()
            # Add additionalProperties if specified
            if self.additional_properties is not None:
                input_schema['additionalProperties'] = self.additional_properties
            result['inputSchema'] = input_schema
        if self.output_schema:
            result['outputSchema'] = self.output_schema
        if self.annotations:
            result['annotations'] = self.annotations.to_dict()

        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Tool(name='{self.name}', title='{self.title}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Tool(name='{self.name}', title='{self.title}', description='{self.description}')"

    @classmethod
    def create_simple(
        cls,
        name: str,
        description: str,
        input_type: str = "object",
        **kwargs
    ) -> 'Tool':
        """Create a simple tool with basic input schema."""
        input_schema = {
            "type": input_type,
            "properties": {},
            "required": []
        }

        return cls(
            name=name,
            description=description,
            input_schema=input_schema,
            **kwargs
        )

    @classmethod
    def create_with_string_input(
        cls,
        name: str,
        description: str,
        input_param_name: str = "input",
        input_param_description: str = "Input parameter",
        **kwargs
    ) -> 'Tool':
        """Create a tool that accepts a single string input."""
        tool = cls.create_simple(name, description, **kwargs)
        tool.add_input_property(
            input_param_name,
            {
                "type": "string",
                "description": input_param_description
            }
        ).add_required_input(input_param_name)

        return tool

    @classmethod
    def create_with_number_input(
        cls,
        name: str,
        description: str,
        input_param_name: str = "value",
        input_param_description: str = "Numeric input parameter",
        **kwargs
    ) -> 'Tool':
        """Create a tool that accepts a single number input."""
        tool = cls.create_simple(name, description, **kwargs)
        tool.add_input_property(
            input_param_name,
            {
                "type": "number",
                "description": input_param_description
            }
        ).add_required_input(input_param_name)

        return tool
