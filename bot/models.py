from sqlalchemy import Column, Integer, BigInteger, Float, String
from bot.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    balance = Column(Float, default=0.0)

class BankCard(Base):
    __tablename__ = "bank_card"

    id = Column(Integer, primary_key=True)
    card_number = Column(String(32), nullable=False)