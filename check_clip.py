import asyncio
from sqlalchemy import select
from app.models.clip import Clip
from app.database import AsyncSessionLocal

async def f():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Clip).order_by(Clip.created_at.desc()).limit(1))
        clip = result.scalar_one()
        print(f"Clip ID: {clip.id}")
        print(f"File path: {clip.file_path}")

asyncio.run(f())
