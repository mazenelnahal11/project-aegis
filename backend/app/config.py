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

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"

    cors_origin: str = "http://localhost:5173"

    db_path: Path = Path(__file__).resolve().parent.parent / "aegis.db"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
