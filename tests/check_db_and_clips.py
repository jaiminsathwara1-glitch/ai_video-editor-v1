import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.project import Project
from app.models.clip import Clip

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Project))
        projects = res.scalars().all()
        print(f"--- Projects ({len(projects)}) ---")
        for p in projects:
            print(f"ID: {p.id}, Name: {p.name}")
            
        res_clips = await db.execute(select(Clip))
        clips = res_clips.scalars().all()
        print(f"\n--- Clips ({len(clips)}) ---")
        for c in clips:
            print(f"ID: {c.id}, ProjectID: {c.project_id}, Filename: {c.filename}, Status: {c.status}")

if __name__ == "__main__":
    asyncio.run(main())
