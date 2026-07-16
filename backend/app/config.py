from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    ml_app_id: str = ""
    ml_client_secret: str = ""
    ml_access_token: str = ""
    ml_refresh_token: str = ""
    ml_user_id: str = ""
    secret_key: str = "dev-secret"
    internal_service_key: str = ""  # chave máquina-a-máquina p/ rotina agendada (não é login de usuário)
    uploads_dir: str = "/data/uploads"
    public_base_url: str = "https://clemerson-production.up.railway.app"  # p/ montar URL pública das fotos (ML exige URL absoluta)
    google_client_id: str = ""  # OAuth Client ID gerado no Google Cloud Console pelo Clemerson

    class Config:
        env_file = ".env"

settings = Settings()
