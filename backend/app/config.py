from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    ml_app_id: str = ""
    ml_client_secret: str = ""
    ml_access_token: str = ""
    ml_refresh_token: str = ""
    ml_user_id: str = ""
    secret_key: str = "dev-secret"

    class Config:
        env_file = ".env"

settings = Settings()
