import asyncio
import traceback
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.clip import Clip

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Clip))
        clips = res.scalars().all()
        if not clips:
            print("No clips found in database.")
            return
        
        target_clip = clips[0]
        print(f"Attempting to delete clip: {target_clip.id} ({target_clip.filename})")
        
        try:
            # Replicate route deletion logic:
            # Clean up physical files from disk
            from pathlib import Path
            for path_str in (target_clip.file_path, target_clip.thumbnail_path, target_clip.trimmed_file_path):
                if path_str:
                    p = Path(path_str)
                    print(f"Unlinking file path: {p}")
                    try:
                        p.unlink(missing_ok=True)
                    except Exception as e:
                        print(f"Failed to unlink {p}: {e}")
            
            print("Deleting clip from session...")
            await db.delete(target_clip)
            print("Committing transaction...")
            await db.commit()
            print("Success! Clip deleted from DB.")
        except Exception as e:
            print("Error occurred during deletion:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
