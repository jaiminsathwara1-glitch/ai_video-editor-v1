"""
Tests for project CRUD endpoints.
"""
import pytest


@pytest.mark.asyncio
async def test_create_project(client):
    resp = await client.post("/api/v1/projects/", json={"name": "Test Project"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Project"
    assert data["status"] == "created"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client):
    await client.post("/api/v1/projects/", json={"name": "P1"})
    await client.post("/api/v1/projects/", json={"name": "P2"})
    resp = await client.get("/api/v1/projects/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    resp = await client.get("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client):
    create_resp = await client.post("/api/v1/projects/", json={"name": "Old Name"})
    pid = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/projects/{pid}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_project(client):
    create_resp = await client.post("/api/v1/projects/", json={"name": "To Delete"})
    pid = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/projects/{pid}")
    assert del_resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{pid}")
    assert get_resp.status_code == 404
