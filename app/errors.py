"""Typed errors shared across services."""


class UnknownStateError(ValueError):
    """The location is not a state or union territory in the population table."""

    def __init__(self, state: str):
        super().__init__(f"No population data for state or UT: {state!r}")
        self.state = state
