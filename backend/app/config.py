from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_token: str = Field("change-me-to-a-long-random-string", alias="ADMIN_TOKEN")
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    openai_api_base: Optional[str] = Field(None, alias="OPENAI_API_BASE")

    app_data_dir: str = Field("/opt/routergeist/data", alias="APP_DATA_DIR")
    nucleus_unlock: bool = Field(False, alias="NUCLEUS_UNLOCK")
    allow_full_device_wipe: bool = Field(False, alias="ALLOW_FULL_DEVICE_WIPE")

    wifi_wan_ssids: List[str] = Field(default_factory=list, alias="WIFI_WAN_SSIDS")
    wifi_wan_psks: List[str] = Field(default_factory=list, alias="WIFI_WAN_PSKS")

    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8080, alias="PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    secret_key: str | None = Field(None, alias="SECRET_KEY")
    admin_username: str | None = Field(None, alias="ADMIN_USERNAME")
    admin_password_hash: str | None = Field(None, alias="ADMIN_PASSWORD_HASH")

    def get_wan_credentials(self) -> List[tuple[str, Optional[str]]]:
        pairs: List[tuple[str, Optional[str]]] = []
        for i, ssid in enumerate(self.wifi_wan_ssids):
            psk: Optional[str] = None
            if i < len(self.wifi_wan_psks):
                psk = self.wifi_wan_psks[i]
            pairs.append((ssid, psk))
        return pairs


settings = Settings()


