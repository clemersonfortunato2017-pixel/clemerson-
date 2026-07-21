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
    # Shopee Open Platform — credencial de APP (uma só, compartilhada por
    # todas as lojas Shopee conectadas). Precisa de aprovação em
    # open.shopee.com antes de existir — sem isso ShopeePlatform fica
    # desconectada e o multi-conta Shopee não ativa.
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    shopee_default_category_id: str = ""  # category_id padrão pra autopeças usadas — mapear antes de publicar de verdade
    anthropic_api_key: str = ""  # esteira automática: identificação por foto + pesquisa de preço, roda sozinha no servidor

    class Config:
        env_file = ".env"

settings = Settings()
