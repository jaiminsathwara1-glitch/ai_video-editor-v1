import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.services.upload_service import init_upload
from app.schemas.clip import ClipRead

async def main():
    async with AsyncSessionLocal() as db:
        try:
            clip = await init_upload(
                db=db,
                project_id="ea84aca7-c4a4-4ea1-99d9-0dcf3217e82a",
                filename="test.mp4",
                file_size=100,
                mime_type="video/mp4",
                total_chunks=1,
            )
            print("init_upload Success:", clip.id)
            read_model = ClipRead.model_validate(clip)
            print("Validate success", read_model)
            await db.commit()
            print("Commit success")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())