from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from pzsd_bot.constants import DB_CONNECTION_STR

engine = create_async_engine(DB_CONNECTION_STR)
Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
