"""
analytics/trackers/registry.py
--------------------------------
Central registry mapping tracker names to their instances.

Adding a new tracker
--------------------
    1. Create ``analytics/trackers/my_tracker.py`` with a class
       subclassing ``BaseTracker``.
    2. Add one line here:
            register(MyTracker())
    3. Done. Access it anywhere via:
            from analytics.trackers import registry
            registry.get("my_tracker_name").record(...)
"""

from .base import BaseTracker
from .click_tracker import ClickTracker
from .progress_tracker import ProgressTracker


class TrackerRegistry:
    def __init__(self):
        self._trackers: dict[str, BaseTracker] = {}

    def register(self, tracker: BaseTracker) -> None:
        if not tracker.name:
            raise ValueError(f"{tracker.__class__.__name__} must define a non-empty `name`.")
        self._trackers[tracker.name] = tracker

    def get(self, name: str) -> BaseTracker:
        try:
            return self._trackers[name]
        except KeyError:
            available = list(self._trackers.keys())
            raise KeyError(
                f"No tracker named '{name}'. Available: {available}"
            ) from None

    def all(self) -> list[BaseTracker]:
        return list(self._trackers.values())

    def names(self) -> list[str]:
        return list(self._trackers.keys())


# ------------------------------------------------------------------ #
#  Singleton registry — import this everywhere                        #
# ------------------------------------------------------------------ #
registry = TrackerRegistry()
registry.register(ClickTracker())
registry.register(ProgressTracker())

# Convenience direct references (avoids registry.get("click") boilerplate)
click_tracker: ClickTracker = registry.get("click")
progress_tracker: ProgressTracker = registry.get("progress")
