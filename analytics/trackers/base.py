"""
analytics/trackers/base.py
--------------------------
Base class for all tracker types.

To add a new tracking concern:

    1. Create a new file, e.g. ``analytics/trackers/quiz_tracker.py``.
    2. Subclass ``BaseTracker`` and implement ``record()``.
    3. Register it in ``analytics/trackers/registry.py``.
    4. (Optional) Add a convenience method to ``AnalyticsService``
       in ``analytics/services/facade.py``.

That's it — no existing code needs to change.
"""

from abc import ABC, abstractmethod


class BaseTracker(ABC):
    """
    Minimal contract every tracker must satisfy.

    Trackers are stateless helpers; construct them fresh or treat them as
    singletons — they hold no per-request state.
    """

    # Human-readable name shown in registry listings / logs.
    name: str = ""

    @abstractmethod
    def record(self, **kwargs):
        """
        Persist one tracking event/record.

        Concrete implementations define their own keyword arguments;
        the signature is intentionally open so each tracker can declare
        exactly what it needs without fighting a fixed interface.
        """
        raise NotImplementedError
