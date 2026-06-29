from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

PLATFORMS = ["mercadolivre", "shopee", "amazon", "balcao"]
PAYMENT_METHODS = ["dinheiro", "pix", "cartao_debito", "cartao_credito", "boleto", "prazo"]

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    platform_order_id = Column(String(100), unique=True, index=True, nullable=True)
    buyer_name = Column(String(200))
    buyer_phone = Column(String(30))
    total = Column(Float, nullable=False, default=0)
    cost_total = Column(Float, default=0)          # custo total dos itens
    profit = Column(Float, default=0)              # lucro bruto
    profit_pct = Column(Float, default=0)          # margem %
    payment_method = Column(String(50))            # dinheiro, pix, cartao_credito, etc
    payment_fee_pct = Column(Float, default=0)     # taxa da plataforma/operadora %
    payment_fee_value = Column(Float, default=0)   # valor da taxa
    net_total = Column(Float, default=0)           # total líquido após taxa
    status = Column(String(50), default="completed")
    notes = Column(Text)
    sold_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    unit_cost = Column(Float, default=0)
    total_price = Column(Float, nullable=False)
    total_cost = Column(Float, default=0)
    margin_pct = Column(Float, default=0)

    sale = relationship("Sale", back_populates="items")
    part = relationship("Part")
