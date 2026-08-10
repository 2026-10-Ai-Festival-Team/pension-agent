from src.generation.fake import FakeGenerator
from src.generation.hcx import HyperClovaXGenerator
def build_answer_generator(settings, transport=None, rate_limiter=None):
    if settings.generator_backend=="fake": return FakeGenerator()
    if settings.generator_backend=="hcx":
        if not all((settings.hcx_api_key,settings.hcx_model,settings.hcx_base_url)): raise ValueError("HCX configuration is incomplete")
        return HyperClovaXGenerator(config=settings,transport=transport,rate_limiter=rate_limiter)
    raise ValueError("Unsupported generator backend")
