import os
from dataclasses import dataclass
@dataclass(frozen=True)
class GenerationSettings:
    environment:str="development"; generator_backend:str="fake"; hcx_api_key:str=""; hcx_model:str=""; hcx_base_url:str=""; timeout_seconds:float=30; max_retries:int=2
    @classmethod
    def from_env(cls):
        value=cls(os.getenv("APP_ENV",os.getenv("ENVIRONMENT","development")),os.getenv("GENERATOR_BACKEND","fake"),os.getenv("HCX_API_KEY",""),os.getenv("HCX_MODEL",""),os.getenv("HCX_BASE_URL",os.getenv("HCX_API_URL","")),float(os.getenv("HCX_TIMEOUT_SECONDS","30")),int(os.getenv("HCX_MAX_RETRIES","2")))
        if value.environment in {"production","evaluation"} and value.generator_backend != "hcx": raise RuntimeError("HCX generator is required in evaluation mode.")
        return value
