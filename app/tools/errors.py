class ToolExecutionError(Exception):
    def __init__(self, *, code: str, message: str, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class RetryableToolExecutionError(ToolExecutionError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(code=code, message=message, retryable=True)


class TerminalToolExecutionError(ToolExecutionError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(code=code, message=message, retryable=False)
