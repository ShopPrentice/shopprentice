"""
Task Manager Module

Provides a TaskManager class for handling custom events and task execution
within the Fusion 360 environment.
"""

import json
import uuid
from typing import Dict, Callable, Any, Optional

try:
    import adsk.core
    app = adsk.core.Application.get()
except ImportError:
    app = None


class TaskManager:
    """
    TaskManager class for handling custom events and task execution.

    Acts as a singleton with class methods for global access.
    Posts tasks with callbacks that execute on the Fusion 360 main thread
    via custom events.
    """

    _instance = None
    _event_handler = None
    _custom_event = None
    _pending_tasks: Dict[str, Dict[str, Any]] = {}
    _is_running = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._event_handler = None
            self._custom_event = None
            self._pending_tasks = {}
            self._is_running = False
            self._initialized = True

    @classmethod
    def start(cls) -> bool:
        """Start the TaskManager by registering a custom event and handler."""
        if not app:
            print("TaskManager: Fusion 360 application not available")
            return False

        if cls._is_running:
            print("TaskManager: Already running")
            return True

        try:
            cls._custom_event = app.registerCustomEvent('ShopPrentice.TaskManagerEvent')

            cls._event_handler = TaskEventHandler(cls._pending_tasks)
            cls._custom_event.add(cls._event_handler)

            cls._is_running = True
            if app:
                app.log("TaskManager: Started successfully")
            return True

        except Exception as e:
            print(f"TaskManager: Failed to start - {str(e)}")
            if app:
                app.log(f"TaskManager: Failed to start - {str(e)}")
            return False

    @classmethod
    def stop(cls) -> bool:
        """Stop the TaskManager by removing the event handler."""
        if not cls._is_running:
            print("TaskManager: Not running")
            return True

        try:
            if cls._custom_event and cls._event_handler:
                cls._custom_event.remove(cls._event_handler)
                cls._event_handler = None
                cls._custom_event = None

            cls._pending_tasks.clear()
            cls._is_running = False

            if app:
                app.log("TaskManager: Stopped successfully")
            return True

        except Exception as e:
            print(f"TaskManager: Failed to stop - {str(e)}")
            if app:
                app.log(f"TaskManager: Failed to stop - {str(e)}")
            return False

    @classmethod
    def post(cls, command: str, callback: Callable[[Dict[str, Any]], None], data: Dict[str, Any]) -> Optional[str]:
        """Post a task with a callback to be executed on the main thread."""
        if not cls._is_running:
            print("TaskManager: Not running, cannot post task")
            return None

        if not callable(callback):
            print("TaskManager: Callback must be callable")
            return None

        try:
            task_id = str(uuid.uuid4())

            cls._pending_tasks[task_id] = {
                'command': command,
                'callback': callback,
                'data': data
            }

            event_data = {
                'task_id': task_id,
                'command': command,
                'data': data
            }

            app.fireCustomEvent(cls._custom_event.eventId, json.dumps(event_data))
            app.log(f"TaskManager: Posted task {task_id} with command '{command}'")

            return task_id

        except Exception as e:
            print(f"TaskManager: Failed to post task - {str(e)}")
            app.log(f"TaskManager: Failed to post task - {str(e)}")
            return None

    @classmethod
    def is_running(cls) -> bool:
        return cls._is_running

    @classmethod
    def get_pending_task_count(cls) -> int:
        return len(cls._pending_tasks)


class TaskEventHandler(adsk.core.CustomEventHandler):
    """Event handler for TaskManager custom events."""

    def __init__(self, pending_tasks: Dict[str, Dict[str, Any]]):
        super().__init__()
        self._pending_tasks = pending_tasks

    def notify(self, args: adsk.core.CustomEventArgs):
        try:
            event_data = json.loads(args.additionalInfo)
            task_id = event_data.get('task_id')
            command = event_data.get('command')
            data = event_data.get('data', {})

            if not task_id or task_id not in self._pending_tasks:
                if app:
                    app.log(f"TaskManager: Unknown task ID {task_id}")
                return

            task_info = self._pending_tasks[task_id]
            callback = task_info['callback']

            try:
                callback(data)
                if app:
                    app.log(f"TaskManager: Executed task {task_id} with command '{command}'")
            except Exception as callback_error:
                print(f"TaskManager: Callback error for task {task_id}: {str(callback_error)}")
                if app:
                    app.log(f"TaskManager: Callback error for task {task_id}: {str(callback_error)}")

            del self._pending_tasks[task_id]

        except json.JSONDecodeError as e:
            print(f"TaskManager: Failed to parse event data: {str(e)}")
            if app:
                app.log(f"TaskManager: Failed to parse event data: {str(e)}")
        except Exception as e:
            print(f"TaskManager: Event handler error: {str(e)}")
            if app:
                app.log(f"TaskManager: Event handler error: {str(e)}")
