from __future__ import annotations


def test_deterministic_scenario_start_step_pause_reset(client):
    catalog = client.get("/api/v1/scenarios")
    assert catalog.status_code == 200
    assert {item["key"] for item in catalog.json()} == {
        "rapid-inundation",
        "camera-degradation",
        "drainage-recovery",
    }

    started = client.post(
        "/api/v1/scenarios/rapid-inundation/start",
        json={
            "siteId": "site-binh-rd-tunnel",
            "speed": 1,
            "autoRun": False,
        },
    )
    assert started.status_code == 201
    run = started.json()
    assert run["status"] == "paused"
    assert run["tickIndex"] == 0

    first_step = client.post(f"/api/v1/scenarios/runs/{run['id']}/step")
    assert first_step.status_code == 200
    tick = first_step.json()
    assert tick["tickIndex"] == 1
    assert tick["waterState"]["maxDepthCm"] == 8.1
    assert tick["weather"]["rainfallMmH"] == 22.0

    paused = client.post(f"/api/v1/scenarios/runs/{run['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    reset = client.post(f"/api/v1/scenarios/runs/{run['id']}/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"
    assert reset.json()["tickIndex"] == 0

    rows = client.get("/api/v1/scenarios/runs").json()
    assert rows[0]["id"] == run["id"]
    assert rows[0]["status"] == "reset"


def test_camera_degradation_exposes_quality_flags(client):
    started = client.post(
        "/api/v1/scenarios/camera-degradation/start",
        json={"siteId": "site-binh-rd-tunnel", "autoRun": False, "speed": 1},
    ).json()
    run_id = started["id"]
    tick = None
    for _ in range(5):
        tick = client.post(f"/api/v1/scenarios/runs/{run_id}/step").json()
    assert tick is not None
    assert tick["tickIndex"] == 5
    assert tick["waterState"]["qualityStatus"] == "filled"
    assert tick["waterState"]["confidence"] == 48.0

    site = client.get("/api/v1/sites/site-binh-rd-tunnel").json()
    assert "TEMPORAL_FILL_USED" in site["latestWater"]["qualityFlags"]
