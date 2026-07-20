from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Part(Base):
    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, index=True)
    # Múltiplos códigos
    code = Column(String(100), unique=True, index=True)          # código interno (legado)
    code_internal = Column(String(100), index=True)              # código interno do estoque
    code_oem = Column(String(100), index=True)                   # código original do fabricante do veículo
    code_manufacturer = Column(String(100), index=True)          # código do fabricante da peça
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    brand = Column(String(100))
    condition = Column(String(20), default="used")  # new, used, refurbished
    cost_price = Column(Float, default=0)
    sale_price = Column(Float, default=0)
    suggested_price = Column(Float, default=0)
    margin_percent = Column(Float, default=0)
    quantity = Column(Integer, default=0)
    # Estoque mínimo e máximo
    min_quantity = Column(Integer, default=1)
    max_quantity = Column(Integer, default=0)
    # Localização física estruturada
    location = Column(String(100))              # campo legado livre
    loc_corridor = Column(String(50))           # Corredor
    loc_shelf = Column(String(50))              # Prateleira
    loc_box = Column(String(50))                # Caixa/Posição
    weight = Column(Float)
    photos = Column(JSON, default=list)
    notes = Column(Text)
    active = Column(Boolean, default=True)
    # Esteira automática de anúncio (upload de foto -> publicação sem revisão humana)
    status = Column(String(20), default="draft")  # draft, processing, published, error
    pipeline_log = Column(JSON, default=list)      # histórico de etapas/decisões/erros da esteira
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    compatibilities = relationship("Compatibility", back_populates="part", cascade="all, delete")
    stock_movements = relationship("StockMovement", back_populates="part", cascade="all, delete")
    marketplace_listings = relationship("MarketplaceListing", back_populates="part", cascade="all, delete")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    year_start = Column(Integer)
    year_end = Column(Integer)
    engine = Column(String(50))
    version = Column(String(100))

    compatibilities = relationship("Compatibility", back_populates="vehicle", cascade="all, delete")


class Compatibility(Base):
    __tablename__ = "compatibilities"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    oem_code = Column(String(100))
    notes = Column(String(255))

    part = relationship("Part", back_populates="compatibilities")
    vehicle = relationship("Vehicle", back_populates="compatibilities")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    type = Column(String(20), nullable=False)  # in, out, adjustment
    quantity = Column(Integer, nullable=False)
    reason = Column(String(100))
    reference = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    part = relationship("Part", back_populates="stock_movements")


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    marketplace = Column(String(50), nullable=False)
    listing_id = Column(String(100), unique=True, index=True)
    url = Column(String(500))
    status = Column(String(50))
    price = Column(Float)
    # Multi-conta: qual PlatformAccount publicou este anúncio. NULL = conta
    # legada/principal do Mercado Livre (MLCredential), não uma linha extra.
    platform_account_id = Column(Integer, ForeignKey("platform_accounts.id"), nullable=True)
    # True quando a sincronização de estoque pra este anúncio esgotou as
    # tentativas depois de uma venda em outra plataforma — precisa de retry manual.
    sync_failed = Column(Boolean, default=False)
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    part = relationship("Part", back_populates="marketplace_listings")
