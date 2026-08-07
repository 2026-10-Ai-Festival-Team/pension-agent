class GenerationError(RuntimeError):
    def __init__(self, message, *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


class GenerationResponseError(GenerationError): pass
class CitationValidationError(GenerationError): pass
