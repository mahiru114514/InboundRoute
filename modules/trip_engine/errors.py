"""行程业务异常；HTTP 层负责将其转换为契约响应。"""

class EngineError(Exception):
    """带 HTTP 状态码与错误码的业务异常，由 HTTP 层转成契约里的响应信封。"""

    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

