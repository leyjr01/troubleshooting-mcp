"""Safe error categories: messages never include external payloads or secrets."""

from enum import StrEnum


class ErrorCode(StrEnum):
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    DATASOURCE_UNAVAILABLE = "datasource_unavailable"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"
    SCHEMA_MAPPING = "schema_mapping"
    EVIDENCE_COLLECTION = "evidence_collection"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    SANITIZATION = "sanitization"


class AGTError(Exception):
    code: ErrorCode = ErrorCode.CONFIGURATION

    def __init__(self) -> None:
        super().__init__(self.code.value)


class ResourceNotFound(AGTError):
    code = ErrorCode.RESOURCE_NOT_FOUND


class ConfigurationError(AGTError):
    code = ErrorCode.CONFIGURATION


class AuthenticationError(AGTError):
    code = ErrorCode.AUTHENTICATION


class AuthorizationError(AGTError):
    code = ErrorCode.AUTHORIZATION


class ConnectionError(AGTError):
    code = ErrorCode.CONNECTION


class TimeoutError(AGTError):
    code = ErrorCode.TIMEOUT


class DataSourceUnavailable(AGTError):
    code = ErrorCode.DATASOURCE_UNAVAILABLE


class GatewayUnavailable(AGTError):
    code = ErrorCode.GATEWAY_UNAVAILABLE


class SchemaMappingError(AGTError):
    code = ErrorCode.SCHEMA_MAPPING


class EvidenceCollectionError(AGTError):
    code = ErrorCode.EVIDENCE_COLLECTION


class UnsupportedCapabilityError(AGTError):
    code = ErrorCode.UNSUPPORTED_CAPABILITY


class SanitizationError(AGTError):
    code = ErrorCode.SANITIZATION
