class RequestError(Exception):
    def __init__(self, message, status_code, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
