from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AEGIS_",
        case_sensitive=False,
        extra="ignore",
    )

    admin_password_hash: str = ""
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24 * 7

    wsl_distro: str = "Ubuntu"
    project_dir_wsl: str = "/mnt/c/Users/mazen/Downloads/aegis_final"

    llm_provider: str = "anthropic"  # 'anthropic' | 'openai_compat'
    llm_api_key: str = ""             # unified key for the active provider
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str = ""            # required for OpenAI-compatible providers

    # Back-compat: prior env var name. Used as a fallback when llm_api_key is unset
    # and llm_provider == 'anthropic'.
    anthropic_api_key: str = ""

    cors_origin: str = "http://localhost:5173"

    # Grace / Slack
    slack_webhook_url: str = ""
    ack_base_url: str = "http://localhost:8000"
    grace_default_minutes: int = 30
    grace_extend_hours: int = 6  # how long a STOP click extends the process
    users_yaml_path: Path = Path(__file__).resolve().parent / "policy" / "users.yaml"
    grace_expiry_check_seconds: int = 30  # how often the background sweeper runs

    db_path: Path = Path(__file__).resolve().parent.parent / "aegis.db"

    @property
    def effective_llm_api_key(self) -> str:
        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return ""

    @property
    def llm_enabled(self) -> bool:
        return bool(self.effective_llm_api_key)


settings = Settings()
