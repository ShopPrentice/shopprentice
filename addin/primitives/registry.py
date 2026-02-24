"""
MCP Registry

This module defines the Registry class for managing MCP Item collections.
Provides a singleton instance for shared use across the add-in.
"""

from typing import List, Dict
from .item import Item


class Registry:
    """
    MCP Registry for managing collections of Item objects.

    Provides a simple interface for registering and accessing MCP primitives
    (Tools, Resources, Prompts) with their handler functions.
    Uses separate dictionaries for each type since names are only unique within a type.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._tools: Dict[str, Item] = {}
        self._resources: Dict[str, Item] = {}
        self._prompts: Dict[str, Item] = {}

    def register(self, item: Item) -> None:
        """
        Register an Item in the registry.

        Args:
            item: Item to register

        Raises:
            ValueError: If item is not an Item instance or name already exists
        """
        if not isinstance(item, Item):
            raise ValueError("Can only register Item instances")

        name = item.get_name()
        item_type = item.get_type()

        if item_type == "tool":
            if name in self._tools:
                raise ValueError(f"Tool with name '{name}' already registered")
            self._tools[name] = item
        elif item_type == "resource":
            if name in self._resources:
                raise ValueError(f"Resource with name '{name}' already registered")
            self._resources[name] = item
        elif item_type == "prompt":
            if name in self._prompts:
                raise ValueError(f"Prompt with name '{name}' already registered")
            self._prompts[name] = item
        else:
            raise ValueError(f"Unknown item type: {item_type}")

    def unregister_tool(self, name: str) -> Item:
        """
        Unregister a tool from the registry.

        Args:
            name: Name of the tool to unregister

        Returns:
            The unregistered tool Item

        Raises:
            KeyError: If tool with name is not found
        """
        if name not in self._tools:
            raise KeyError(f"Tool with name '{name}' not found")

        return self._tools.pop(name)

    def unregister_resource(self, name: str) -> Item:
        """
        Unregister a resource from the registry.

        Args:
            name: Name of the resource to unregister

        Returns:
            The unregistered resource Item

        Raises:
            KeyError: If resource with name is not found
        """
        if name not in self._resources:
            raise KeyError(f"Resource with name '{name}' not found")

        return self._resources.pop(name)

    def unregister_prompt(self, name: str) -> Item:
        """
        Unregister a prompt from the registry.

        Args:
            name: Name of the prompt to unregister

        Returns:
            The unregistered prompt Item

        Raises:
            KeyError: If prompt with name is not found
        """
        if name not in self._prompts:
            raise KeyError(f"Prompt with name '{name}' not found")

        return self._prompts.pop(name)

    def get_tool(self, name: str) -> Item:
        """
        Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            The tool Item with the specified name

        Raises:
            KeyError: If tool with name is not found
        """
        if name not in self._tools:
            raise KeyError(f"Tool with name '{name}' not found")

        return self._tools[name]

    def get_resource(self, name: str) -> Item:
        """
        Get a resource by name.

        Args:
            name: Name of the resource

        Returns:
            The resource Item with the specified name

        Raises:
            KeyError: If resource with name is not found
        """
        if name not in self._resources:
            raise KeyError(f"Resource with name '{name}' not found")

        return self._resources[name]

    def get_prompt(self, name: str) -> Item:
        """
        Get a prompt by name.

        Args:
            name: Name of the prompt

        Returns:
            The prompt Item with the specified name

        Raises:
            KeyError: If prompt with name is not found
        """
        if name not in self._prompts:
            raise KeyError(f"Prompt with name '{name}' not found")

        return self._prompts[name]

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool exists in the registry.

        Args:
            name: Name of the tool to check

        Returns:
            True if tool exists, False otherwise
        """
        return name in self._tools

    def has_resource(self, name: str) -> bool:
        """
        Check if a resource exists in the registry.

        Args:
            name: Name of the resource to check

        Returns:
            True if resource exists, False otherwise
        """
        return name in self._resources

    def has_prompt(self, name: str) -> bool:
        """
        Check if a prompt exists in the registry.

        Args:
            name: Name of the prompt to check

        Returns:
            True if prompt exists, False otherwise
        """
        return name in self._prompts

    def get_tools(self) -> List[Item]:
        """
        Get all registered tool items.

        Returns:
            List of tool items
        """
        return list(self._tools.values())

    def get_resources(self) -> List[Item]:
        """
        Get all registered resource items.

        Returns:
            List of resource items
        """
        return list(self._resources.values())

    def get_prompts(self) -> List[Item]:
        """
        Get all registered prompt items.

        Returns:
            List of prompt items
        """
        return list(self._prompts.values())

    def get_tool_names(self) -> List[str]:
        """
        Get names of all registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_resource_names(self) -> List[str]:
        """
        Get names of all registered resources.

        Returns:
            List of resource names
        """
        return list(self._resources.keys())

    def get_prompt_names(self) -> List[str]:
        """
        Get names of all registered prompts.

        Returns:
            List of prompt names
        """
        return list(self._prompts.keys())

    def get_all_names(self) -> List[str]:
        """
        Get names of all registered items.

        Returns:
            List of all item names
        """
        return self.get_tool_names() + self.get_resource_names() + self.get_prompt_names()

    def clear(self) -> None:
        """Clear all registered items."""
        self._tools.clear()
        self._resources.clear()
        self._prompts.clear()

    def count(self) -> int:
        """
        Get the total number of registered items.

        Returns:
            Number of registered items
        """
        return len(self._tools) + len(self._resources) + len(self._prompts)

    def count_by_type(self) -> Dict[str, int]:
        """
        Get count of items by type.

        Returns:
            Dictionary with counts for each type
        """
        return {
            "tool": len(self._tools),
            "resource": len(self._resources),
            "prompt": len(self._prompts)
        }

    def __len__(self) -> int:
        """Return the number of registered items."""
        return self.count()

    def __str__(self) -> str:
        """String representation for debugging."""
        counts = self.count_by_type()
        return (f"Registry(tools={counts['tool']}, resources={counts['resource']}, "
                f"prompts={counts['prompt']})")

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"Registry(tools={self._tools}, resources={self._resources}, "
                f"prompts={self._prompts})")


# Singleton instance for shared use across the add-in
_registry_instance: Registry = None


def get_registry() -> Registry:
    """
    Get the singleton registry instance.
    
    Returns:
        The shared Registry instance
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = Registry()
    return _registry_instance


def reset_registry() -> None:
    """
    Reset the singleton registry instance.
    Useful for testing or when you need a fresh registry.
    """
    global _registry_instance
    _registry_instance = None


# Convenience functions that operate on the singleton instance
def register(item: Item) -> None:
    """Register an item in the singleton registry."""
    get_registry().register(item)


def get_tool(name: str) -> Item:
    """Get a tool from the singleton registry."""
    return get_registry().get_tool(name)


def get_resource(name: str) -> Item:
    """Get a resource from the singleton registry."""
    return get_registry().get_resource(name)


def get_prompt(name: str) -> Item:
    """Get a prompt from the singleton registry."""
    return get_registry().get_prompt(name)


def has_tool(name: str) -> bool:
    """Check if a tool exists in the singleton registry."""
    return get_registry().has_tool(name)


def has_resource(name: str) -> bool:
    """Check if a resource exists in the singleton registry."""
    return get_registry().has_resource(name)


def has_prompt(name: str) -> bool:
    """Check if a prompt exists in the singleton registry."""
    return get_registry().has_prompt(name)


def get_tools() -> List[Item]:
    """Get all tools from the singleton registry."""
    return get_registry().get_tools()


def get_resources() -> List[Item]:
    """Get all resources from the singleton registry."""
    return get_registry().get_resources()


def get_prompts() -> List[Item]:
    """Get all prompts from the singleton registry."""
    return get_registry().get_prompts()


def clear_registry() -> None:
    """Clear all items from the singleton registry."""
    get_registry().clear()


def registry_count() -> int:
    """Get the total count of items in the singleton registry."""
    return get_registry().count()
