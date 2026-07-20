from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.database import Base


class PlatformAccount(Base):
    """Conta extra em qualquer plataforma, além da conta legada/principal do
    Mercado Livre (que continua usando MLCredential + F:\\...\\ml_tokens.json,
    intocada de propósito). Multi-conta: ML pessoa física, Shopee PJ, etc —
    cada linha aqui é uma credencial independente que o motor de publish/sync
    em platform_registry.py itera automaticamente. Adicionar conta nova é só
    inserir linha aqui (via fluxo OAuth em routes/platform_accounts.py), não
    mexe em código."""
    __tablename__ = "platform_accounts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)   # mercadolivre, shopee, amazon, facebook, magalu
    label = Column(String(150), nullable=False)                  # "ML - PF Clemerson", "Shopee - PJ Fortunato"
    external_id = Column(String(100))                            # ML user_id / Shopee shop_id
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    extra = Column(JSON, default=dict)                           # dados específicos da plataforma
    active = Column(Boolean, default=True)
    oauth_state = Column(String(100))                            # anti-CSRF durante o handshake de conexão (nulo depois de confirmado)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PlatformSyncLog(Base):
    """Toda tentativa de propagar estoque/baixa pras outras contas depois de
    uma venda. Peça vendida em 3+ plataformas não pode ficar vendável em duas
    ao mesmo tempo — por isso toda falha fica registrada aqui e sinalizada em
    MarketplaceListing.sync_failed, nunca engolida em silêncio."""
    __tablename__ = "platform_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, index=True)
    listing_id = Column(String(100), index=True)
    marketplace = Column(String(50))
    action = Column(String(30))       # update_stock, close, resolve_account
    attempt = Column(Integer, default=1)
    success = Column(Boolean, default=False)
    detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
