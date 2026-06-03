import asyncio
import traceback
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.project import Project
from app.models.clip import Clip
from app.models.analysis import ClipAnalysis

async def main():
    async with AsyncSessionLocal() as db:
        # Create a test project
        project = Project(name="FK Test Project")
        db.add(project)
        await db.flush()
        
        # Create a test clip
        clip = Clip(
            project_id=project.id,
            filename="fk_test_clip.mp4",
            original_filename="fk_test_clip.mp4",
            file_path="dummy_path.mp4",
            status="analysed"
        )
        db.add(clip)
        await db.flush()
        
        # Create a test analysis
        analysis = ClipAnalysis(
            clip_id=clip.id,
            overall_score=7.5,
            tags=["test"]
        )
        db.add(analysis)
        await db.flush()
        
        print(f"Created project: {project.id}, clip: {clip.id}, analysis: {analysis.id}")
        
        try:
            print("Attempting to delete clip...")
            await db.delete(clip)
            await db.commit()
            print("Success! Clip with analysis deleted successfully.")
        except Exception as e:
            print("Error occurred during deletion:")
            traceback.print_exc()
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(main())
