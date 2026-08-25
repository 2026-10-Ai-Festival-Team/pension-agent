from src.generation.fake import FakeGenerator
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder


def build_answer_generator(settings, transport=None, rate_limiter=None):
    if settings.generator_backend == "fake":
        return FakeGenerator()
    if settings.generator_backend == "hcx":
        if not all((settings.hcx_api_key, settings.hcx_model, settings.hcx_base_url)):
            raise ValueError("HCX configuration is incomplete")
        # HCX-007은 prompt-only JSON 지시보다 Native Structured Outputs가
        # 형식 안정성이 높다. parser/citation validator는 여전히 최종 검증을
        # 수행하므로, API schema가 근거 적합성까지 보장한다고 가정하지 않는다.
        prompt_builder = (
            NativeStructuredOutputPromptBuilder()
            if settings.hcx_model.upper() == "HCX-007"
            else None
        )
        return HyperClovaXGenerator(
            config=settings,
            transport=transport,
            prompt_builder=prompt_builder,
            rate_limiter=rate_limiter,
        )
    raise ValueError("Unsupported generator backend")
