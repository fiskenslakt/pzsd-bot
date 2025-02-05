from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from settings import DB

jobstores = {
    "default": SQLAlchemyJobStore(
        url=f"postgresql+psycopg2://{DB.pguser}:{DB.pgpassword}@{DB.pghost}:{DB.pgport}/{DB.pgdatabase}"
    )
}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="US/Eastern")
