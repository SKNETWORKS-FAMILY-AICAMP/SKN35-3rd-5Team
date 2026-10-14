"""챗봇과 광고문 생성 화면이 공유하는 생성 그래프 진입점."""
from ..domain.schemas import GenerateRequest, GenerateResponse
from ..models.copy_generator import GenerationUnavailable


class UnifiedGenerationService:
    def __init__(self, reviewer):
        self.reviewer = reviewer

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        try:
            return self.reviewer.generate_copy(request)
        except Exception as error:
            raise GenerationUnavailable("광고문 생성·검토에 실패했습니다. 모델과 검색 서버 연결 상태를 확인하고 다시 시도해주세요.") from error
