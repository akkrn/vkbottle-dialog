class DialogError(Exception):
    pass


class UnknownIntent(DialogError):
    pass


class OutdatedIntent(DialogError):
    def __init__(self, stack_key: str = "", *args):
        self.stack_key = stack_key
        super().__init__(*args)


class UnknownState(DialogError):
    pass


class InvalidPayload(DialogError):
    pass


class DialogStackOverflow(DialogError):
    pass


class DialogConfigError(DialogError):
    pass


class CancelEventProcessing(Exception):
    """Сигнал из хендлера: не перерисовывать окно."""
