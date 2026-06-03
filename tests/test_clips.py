"""
Tests for clip CRUD and deletion endpoints, verifying file system unlinking.
"""
import pytest
from pathlib import Path
from sqlalchemy import select
from app.models.clip import Clip


@pytest.mark.asyncio
async def test_delete_clip_cleans_up_files(client, db_session):
    # 1. Create a project
    project_resp = await client.post("/api/v1/projects/", json={"name": "Clip Deletion Test Project"})
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    # 2. Create dummy files on disk
    dummy_video = Path("storage/temp/test_delete_video.mp4")
    dummy_thumb = Path("storage/temp/test_delete_thumb.jpg")
    dummy_trim = Path("storage/temp/test_delete_trim.mp4")

    dummy_video.parent.mkdir(parents=True, exist_ok=True)
    dummy_video.write_text("dummy video content")
    dummy_thumb.write_text("dummy thumb content")
    dummy_trim.write_text("dummy trim content")

    assert dummy_video.exists()
    assert dummy_thumb.exists()
    assert dummy_trim.exists()

    # 3. Create a Clip record in the DB using db_session
    clip = Clip(
        project_id=project_id,
        filename="test_delete_video.mp4",
        original_filename="test_delete_video.mp4",
        file_path=str(dummy_video),
        thumbnail_path=str(dummy_thumb),
        trimmed_file_path=str(dummy_trim),
        status="analysed",
    )
    db_session.add(clip)
    await db_session.commit()
    await db_session.refresh(clip)
    clip_id = clip.id

    # 4. Verify clip exists in database
    result = await db_session.execute(select(Clip).where(Clip.id == clip_id))
    assert result.scalar_one_or_none() is not None

    # 5. Call the delete API endpoint
    delete_resp = await client.delete(f"/api/v1/clips/{clip_id}")
    assert delete_resp.status_code == 204

    # 6. Verify clip is deleted from database
    result = await db_session.execute(select(Clip).where(Clip.id == clip_id))
    assert result.scalar_one_or_none() is None

    # 7. Verify all files have been deleted from disk
    assert not dummy_video.exists(), "Original video was not deleted from disk"
    assert not dummy_thumb.exists(), "Thumbnail was not deleted from disk"
    assert not dummy_trim.exists(), "Trimmed preview was not deleted from disk"
