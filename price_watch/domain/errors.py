"""Application failures shared by storage adapters and their consumers."""


class CardAlreadyExists(ValueError):
    pass


class CardInActiveRun(ValueError):
    pass


class NoCards(ValueError):
    pass


class ConnectorNotAvailable(ValueError):
    pass


class ImportDuringRun(ValueError):
    pass


class VariantOwnershipConflict(ValueError):
    pass
