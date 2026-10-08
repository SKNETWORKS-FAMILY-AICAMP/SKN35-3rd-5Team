"""
[models/judge_factory.py]
설정(JUDGE_BACKEND)에 따라 판정 모델을 생성하고 자동 Fallback을 지원하는 팩토리.
"""
from ..common.config import settings
from ..common.logger import get_logger
from ..domain.rules import RuleEngine
from .base import BaseJudgeModel
from .rule_judge import RuleJudgeModel
from .gpt_judge import GPTJudgeModel
from .ft_judge import FineTunedJudgeModel

logger = get_logger("JudgeFactory")


class JudgeFactory:
    @staticmethod
    def create_judge(rule_engine: RuleEngine | None = None) -> BaseJudgeModel:
        backend = settings.JUDGE_BACKEND
        engine = rule_engine or RuleEngine()

        logger.info(f"판정 모델 백엔드 초기화: {backend}")

        if backend == "rule":
            return RuleJudgeModel(engine)
        elif backend == "gpt":
            return GPTJudgeModel(model_name=settings.OPENAI_MODEL_NAME)
        elif backend == "ft":
            try:
                return FineTunedJudgeModel(adapter_path=settings.FT_ADAPTER_PATH)
            except Exception as e:
                logger.warning(f"FT 모델 로드 실패 ({e}). GPT 백엔드로 자동 Fallback합니다.")
                return GPTJudgeModel(model_name=settings.OPENAI_MODEL_NAME)
        else:
            logger.warning(f"알 수 없는 백엔드 '{backend}'. 기본 Rule 모델을 사용합니다.")
            return RuleJudgeModel(engine)
