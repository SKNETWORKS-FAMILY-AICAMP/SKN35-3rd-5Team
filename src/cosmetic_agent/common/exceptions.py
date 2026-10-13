"""
[common/exceptions.py]
시스템 전역 도메인 커스텀 예외 정의.
"""


class CosmeticAgentError(Exception):
    """기본 도메인 예외"""
    pass


class EvidenceInsufficientError(CosmeticAgentError):
    """근거 조항 검색 부족 예외"""
    pass


class ContractValidationError(CosmeticAgentError):
    """Pydantic 결과 계약 위반 예외"""
    pass


class VerificationFailedError(CosmeticAgentError):
    """제안 문구 수치/효능 대조 실패 예외"""
    pass
