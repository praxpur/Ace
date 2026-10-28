class PlayerError(Exception):
    """An error with an actionable message suitable for the desktop interface."""


class ConfigurationError(PlayerError):
    pass


class DependencyError(PlayerError):
    pass


class UserCancelled(PlayerError):
    pass


class LoginRequired(PlayerError):
    pass


class PageNotReady(PlayerError):
    pass


class CatalogUnavailable(PlayerError):
    pass


class NavigationError(PlayerError):
    pass


class PlaybackError(PlayerError):
    pass
