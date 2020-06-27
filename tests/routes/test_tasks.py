import json

from tests.routes import create_default_asset


def test_tasks_success(client, db):
    """Basic test to make sure task routes behave correctly."""
    # Add a dataset, version, and asset
    dataset = "test"
    version = "v20200626"

    asset = create_default_asset(client, dataset, version)
    asset_id = asset["asset_id"]

    # Verify that the asset and version are in state "pending"
    version_resp = client.get(f"/meta/{dataset}/{version}")
    assert version_resp.json()["data"]["status"] == "pending"

    asset_resp = client.get(f"/meta/{dataset}/{version}/assets/{asset_id}")
    assert asset_resp.json()["data"]["status"] == "pending"

    # At this point there should be a bunch of tasks started for the default
    # asset, though they won't be able to report their status because the
    # full application isn't up and listening. That's fine, we're going to
    # update the tasks via the task status endpoint the same way the Batch
    # tasks would (though via the test client instead of curl).

    # Verify the existence of the tasks, and that they each have only the
    # initial changelog with status "pending"
    existing_tasks = client.get(f"/tasks/assets/{asset_id}").json()["data"]
    assert len(existing_tasks) == 7
    for task in existing_tasks:
        assert len(task["change_log"]) == 1
        assert task["change_log"][0]["status"] == "pending"

    # Arbitrarily choose a task and add a changelog.
    sample_task_id = existing_tasks[0]["task_id"]
    patch_payload = {
        "change_log": [
            {
                "date_time": "2020-06-25 14:30:00",
                "status": "success",
                "message": "All finished!",
                "detail": "None",
            }
        ]
    }
    patch_resp = client.patch(
        f"/tasks/{sample_task_id}", data=json.dumps(patch_payload)
    )
    assert patch_resp.json()["status"] == "success"

    # Verify the task has two changelogs now.
    get_resp = client.get(f"/tasks/{sample_task_id}")
    assert len(get_resp.json()["data"]["change_log"]) == 2

    # Verify that the asset and version are still in state "pending"
    version_resp = client.get(f"/meta/{dataset}/{version}")
    assert version_resp.json()["data"]["status"] == "pending"

    asset_resp = client.get(f"/meta/{dataset}/{version}/assets/{asset_id}")
    assert asset_resp.json()["data"]["status"] == "pending"

    # Update the rest of the tasks with changelogs of status "success"
    # Verify that the commpletion status is propagated to the asset and version
    for task in existing_tasks[1:]:
        patch_payload = {
            "change_log": [
                {
                    "date_time": "2020-06-25 14:30:00",
                    "status": "success",
                    "message": "All finished!",
                    "detail": "None",
                }
            ]
        }
        patch_resp = client.patch(
            f"/tasks/{task['task_id']}", data=json.dumps(patch_payload)
        )
        assert patch_resp.json()["status"] == "success"

    version_resp = client.get(f"/meta/{dataset}/{version}")
    assert version_resp.json()["data"]["status"] == "saved"

    asset_resp = client.get(f"/meta/{dataset}/{version}/assets/{asset_id}")
    assert asset_resp.json()["data"]["status"] == "saved"


def test_tasks_failure(client, db):
    """Basic test to make sure task routes behave correctly."""
    # Add a dataset, version, and asset
    dataset = "test"
    version = "v20200626"

    asset = create_default_asset(client, dataset, version)
    asset_id = asset["asset_id"]

    # Verify that the asset and version are in state "pending"
    version_resp = client.get(f"/meta/{dataset}/{version}")
    assert version_resp.json()["data"]["status"] == "pending"

    asset_resp = client.get(f"/meta/{dataset}/{version}/assets/{asset_id}")
    assert asset_resp.json()["data"]["status"] == "pending"

    # At this point there should be a bunch of tasks started for the default
    # asset, though they won't be able to report their status because the
    # full application isn't up and listening. That's fine, we're going to
    # update the tasks via the task status endpoint the same way the Batch
    # tasks would (though via the test client instead of curl).

    # Verify the existence of the tasks, and that they each have only the
    # initial changelog with status "pending"
    existing_tasks = client.get(f"/tasks/assets/{asset_id}").json()["data"]

    assert len(existing_tasks) == 7
    for task in existing_tasks:
        assert len(task["change_log"]) == 1
        assert task["change_log"][0]["status"] == "pending"

    # Arbitrarily choose a task and add a changelog indicating the task
    # failed.
    sample_task_id = existing_tasks[0]["task_id"]
    patch_payload = {
        "change_log": [
            {
                "date_time": "2020-06-25 14:30:00",
                "status": "failed",
                "message": "Bad Luck!",
                "detail": "None",
            }
        ]
    }
    patch_resp = client.patch(
        f"/tasks/{sample_task_id}", data=json.dumps(patch_payload)
    )
    assert patch_resp.json()["status"] == "success"

    # Verify that the asset and version have been changed to state "failed"
    version_resp = client.get(f"/meta/{dataset}/{version}")
    assert version_resp.json()["data"]["status"] == "failed"
