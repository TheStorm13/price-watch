"""Application failures shared by storage adapters and their consumers."""


class CardAlreadyExists(ValueError):
    pass


class CardInActiveRun(ValueError):
    pass


class NoCards(ValueError):
    pass


class ImportDuringRun(ValueError):
    pass


class VariantOwnershipConflict(ValueError):
    pass


class ThumbnailError(Exception):
    """Unavailable image source or cache; the UI shows its image placeholder."""
