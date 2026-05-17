def test_project_crud(client):
    created = client.post("/projects", json={"name": "Demo", "description": "Initial project"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Demo"

    listed = client.get("/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Initial project"

    updated = client.patch(f"/projects/{project['id']}", json={"name": "Updated"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated"

    deleted = client.delete(f"/projects/{project['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/projects/{project['id']}")
    assert missing.status_code == 404
