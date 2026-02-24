"""
MCP Resource Schema

This module defines the Resource class for MCP transport arguments.
"""

import json
from typing import Optional


class Resource:
    """
    MCP Resource schema for defining resource metadata.

    Provides a simple interface for creating and managing MCP resource definitions
    that can be easily converted to JSON format.
    """

    def __init__(
        self,
        uri: str,
        name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        size: Optional[int] = None,
        uri_template: Optional[str] = None
    ):
        """
        Initialize Resource with required uri and optional fields.

        Args:
            uri: Unique identifier for the resource
            name: The name of the resource
            title: Optional human-readable name for display
            description: Optional description
            mime_type: Optional MIME type
            size: Optional size in bytes
            uri_template: Optional URI template with variables (e.g., "fusion://screenshot/{width}x{height}")
        """
        self.uri = uri
        self.name = name
        self.title = title
        self.description = description
        self.mime_type = mime_type
        self.size = size
        self.uri_template = uri_template

    def set_name(self, name: str) -> 'Resource':
        """Set the resource name. Returns self for method chaining."""
        self.name = name
        return self

    def set_title(self, title: str) -> 'Resource':
        """Set the resource title. Returns self for method chaining."""
        self.title = title
        return self

    def set_description(self, description: str) -> 'Resource':
        """Set the resource description. Returns self for method chaining."""
        self.description = description
        return self

    def set_mime_type(self, mime_type: str) -> 'Resource':
        """Set the MIME type. Returns self for method chaining."""
        self.mime_type = mime_type
        return self

    def set_size(self, size: int) -> 'Resource':
        """Set the size in bytes. Returns self for method chaining."""
        if size is not None and size < 0:
            raise ValueError("Size must be non-negative")
        self.size = size
        return self

    def set_uri_template(self, template: str) -> 'Resource':
        """Set the URI template. Returns self for method chaining."""
        self.uri_template = template
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {}

        # For templates, use uriTemplate instead of uri
        if self.uri:
            result['uri'] = self.uri
        elif self.uri_template:
            result['uriTemplate'] = self.uri_template

        if self.name:
            result['name'] = self.name
        if self.title:
            result['title'] = self.title
        if self.description:
            result['description'] = self.description
        if self.mime_type:
            result['mimeType'] = self.mime_type
        if self.size is not None:
            result['size'] = self.size

        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Resource(uri='{self.uri}', name='{self.name}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"Resource(uri='{self.uri}', name='{self.name}', "
                f"title='{self.title}', description='{self.description}')")

    @classmethod
    def create_simple(cls, uri: str, name: str, **kwargs) -> 'Resource':
        """Create a simple resource with basic information."""
        return cls(uri=uri, name=name, **kwargs)

    @classmethod
    def create_text_resource(
        cls,
        uri: str,
        name: str,
        description: Optional[str] = None,
        **kwargs
    ) -> 'Resource':
        """Create a text resource with text/plain MIME type."""
        return cls(
            uri=uri,
            name=name,
            description=description,
            mime_type="text/plain",
            **kwargs
        )

    @classmethod
    def create_json_resource(
        cls,
        uri: str,
        name: str,
        description: Optional[str] = None,
        **kwargs
    ) -> 'Resource':
        """Create a JSON resource with application/json MIME type."""
        return cls(
            uri=uri,
            name=name,
            description=description,
            mime_type="application/json",
            **kwargs
        )

    @classmethod
    def create_image_resource(
        cls,
        uri: str,
        name: str,
        description: Optional[str] = None,
        **kwargs
    ) -> 'Resource':
        """Create an image resource with image/* MIME type."""
        return cls(
            uri=uri,
            name=name,
            description=description,
            mime_type="image/png",  # Default to PNG
            **kwargs
        )
