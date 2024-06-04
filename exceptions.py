class TokenMissError(Exception):
    pass


class RequestError(Exception):
    pass


class JsonDecodeError(Exception):
    pass


class CurrentDateError(Exception):
    pass


class CurrentDateKeyError(CurrentDateError):
    pass


class CurrentDateKeyTypeError(CurrentDateError):
    pass
