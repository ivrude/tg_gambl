from sqlalchemy import Column, Integer, BigInteger, Float
from bot.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    balance = Column(Float, default=0.0)
