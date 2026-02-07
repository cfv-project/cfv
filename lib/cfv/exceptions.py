"""Exception classes for cfv."""


class CFVException(Exception):
    pass


class CFVValueError(CFVException):
    # invalid argument in user input
    pass


class CFVNameError(CFVException):
    # invalid command in user input
    pass


class CFVSyntaxError(CFVException):
    # error in user input
    pass


class FilenameError(ValueError):
    pass


class MissingDependencyError(RuntimeError):
    pass
