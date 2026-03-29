"""Custom exception hierarchy for Chatbot BĐS Viva."""


class ChatbotVivaError(Exception):
    """Base exception for all chatbot errors."""
    pass


class ConfigurationError(ChatbotVivaError):
    """Raised when configuration is invalid or missing."""
    pass


class RetrievalError(ChatbotVivaError):
    """Raised when document retrieval fails."""
    pass


class LLMError(ChatbotVivaError):
    """Raised when LLM invocation fails."""
    pass


class CacheError(ChatbotVivaError):
    """Raised when cache operations fail."""
    pass


class VectorStoreError(RetrievalError):
    """Raised when vector store operations fail."""
    pass


class DocumentProcessingError(ChatbotVivaError):
    """Raised when document loading or processing fails."""
    pass


class DatabaseError(ChatbotVivaError):
    """Raised when database operations fail."""
    pass


class ConversationNotFoundError(DatabaseError):
    """Raised when a conversation does not exist."""
    pass


class AuthenticationError(ChatbotVivaError):
    """Raised when authentication fails."""
    pass


class UserAlreadyExistsError(AuthenticationError):
    """Raised when registering with an existing email."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are wrong."""
    pass


class TokenError(AuthenticationError):
    """Raised when token verification fails."""
    pass


class ForbiddenError(ChatbotVivaError):
    """Raised when user lacks required permissions."""
    pass
