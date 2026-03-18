"""
analytics/trackers/click_tracker.py
------------------------------------
Handles click, view, and submit events via the Event model.
"""

from analytics.models import Event
from .base import BaseTracker


class ClickTracker(BaseTracker):
    """
    Records user interaction events (clicks, views, submits, or any
    custom event_type string).

    Usage
    -----
        tracker = ClickTracker()

        # Simple click
        tracker.record(
            feature="workspace_btn",
            feature_path=["dashboard", "sidebar", "workspace_btn"],
            user=request.user_obj,
        )

        # Custom event type
        tracker.record(
            event_type="hover",
            feature="tooltip",
            user=request.user_obj,
        )
    """

    name = "click"

    def record(
        self,
        feature: str,
        *,
        event_type: str = Event.CLICK,
        feature_path=None,
        metadata: dict = None,
        user=None,
        client=None,
    ) -> Event:
        """
        Persist an interaction event.

        Args:
            feature:     Leaf feature name (e.g. "save_button").
            event_type:  Defaults to Event.CLICK. Pass Event.VIEW or
                         Event.SUBMIT, or any arbitrary string for custom types.
            feature_path: Pipe-delimited string or list describing the full
                          hierarchy (e.g. ["settings", "profile", "save_button"]).
            metadata:    Free-form dict stored alongside the event.
            user:        User instance.
            client:      ClientUserInfo instance.

        Returns:
            The saved Event instance.
        """
        return Event.track(
            event_type=event_type,
            feature=feature,
            feature_path=feature_path,
            metadata=metadata,
            user=user,
            client=client,
        )

    # ------------------------------------------------------------------ #
    #  Convenience shorthands                                              #
    # ------------------------------------------------------------------ #
    def click(self, feature: str, **kwargs) -> Event:
        return self.record(feature, event_type=Event.CLICK, **kwargs)

    def view(self, feature: str, **kwargs) -> Event:
        return self.record(feature, event_type=Event.VIEW, **kwargs)

    def submit(self, feature: str, **kwargs) -> Event:
        return self.record(feature, event_type=Event.SUBMIT, **kwargs)
