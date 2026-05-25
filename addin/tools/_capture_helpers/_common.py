"""Shared utilities for capture helpers."""

import adsk.core
import adsk.fusion
from contextlib import contextmanager


@contextmanager
def _roll_to_feature(entity, design):
    """Roll timeline to a feature for BRep-dependent property access, then restore."""
    tl = design.timeline
    try:
        entity.timelineObject.rollTo(True)
        yield
    finally:
        tl.moveToEnd()
