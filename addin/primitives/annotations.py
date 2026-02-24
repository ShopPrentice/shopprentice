"""
MCP Annotations Schema

This module defines the Annotations class for MCP transport arguments.
"""

import json
from typing import List, Optional, Union
from datetime import datetime


class Annotations:
    """
    MCP Annotations schema for resource metadata.

    Provides a simple interface for creating and managing MCP annotation data
    that can be easily converted to JSON format.
    """

    def __init__(
        self,
        audience: Optional[List[str]] = None,
        priority: Optional[float] = None,
        last_modified: Optional[Union[str, datetime]] = None
    ):
        """
        Initialize Annotations with optional values.

        Args:
            audience: Array of intended audiences ("user", "assistant")
            priority: Importance value from 0.0 to 1.0
            last_modified: ISO 8601 timestamp string or datetime object
        """
        self.audience = audience or []
        self.priority = priority
        self.last_modified = last_modified

    def set_audience(self, *audiences: str) -> 'Annotations':
        """Set the audience list. Returns self for method chaining."""
        self.audience = list(audiences)
        return self

    def add_audience(self, audience: str) -> 'Annotations':
        """Add an audience to the list. Returns self for method chaining."""
        if audience not in self.audience:
            self.audience.append(audience)
        return self

    def set_priority(self, priority: float) -> 'Annotations':
        """Set the priority value (0.0 to 1.0). Returns self for method chaining."""
        if not 0.0 <= priority <= 1.0:
            raise ValueError("Priority must be between 0.0 and 1.0")
        self.priority = priority
        return self

    def set_last_modified(self, last_modified: Union[str, datetime]) -> 'Annotations':
        """Set the last modified timestamp. Returns self for method chaining."""
        if isinstance(last_modified, datetime):
            self.last_modified = last_modified.isoformat() + 'Z'
        else:
            self.last_modified = last_modified
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {}
        if self.audience:
            result['audience'] = self.audience
        if self.priority is not None:
            result['priority'] = self.priority
        if self.last_modified:
            result['lastModified'] = self.last_modified
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Annotations({self.to_dict()})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"Annotations(audience={self.audience}, priority={self.priority}, "
                f"last_modified={self.last_modified})")

    @classmethod
    def for_user(cls) -> 'Annotations':
        """Create annotations for user audience."""
        return cls().set_audience("user")

    @classmethod
    def for_assistant(cls) -> 'Annotations':
        """Create annotations for assistant audience."""
        return cls().set_audience("assistant")

    @classmethod
    def for_both(cls) -> 'Annotations':
        """Create annotations for both user and assistant audiences."""
        return cls().set_audience("user", "assistant")

    @classmethod
    def high_priority(cls) -> 'Annotations':
        """Create high priority annotations (1.0)."""
        return cls().set_priority(1.0)

    @classmethod
    def low_priority(cls) -> 'Annotations':
        """Create low priority annotations (0.0)."""
        return cls().set_priority(0.0)

    @classmethod
    def now_modified(cls) -> 'Annotations':
        """Create annotations with current timestamp."""
        return cls().set_last_modified(datetime.utcnow())
