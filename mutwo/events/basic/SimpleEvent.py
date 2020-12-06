import numbers

from mutwo.events import abc


class SimpleEvent(abc.Event):
    """Event-Object, which doesn't contain other Event-Objects."""

    def __init__(self, new_duration: numbers.Number):
        self.duration = new_duration

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, new_duration: numbers.Number):
        self._duration = new_duration

    def get_parameter(self, parameter_name: str) -> tuple:
        """Return tuple filled with the value of each event for the asked parameter.

        If an event doesn't posses the asked attribute, 'None' will be added.
        """
        try:
            return (getattr(self, parameter_name),)
        except AttributeError:
            return (None,)
