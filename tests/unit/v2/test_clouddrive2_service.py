from pathlib import Path

from emby115_v2.services.clouddrive2 import (
    CloudDrive2MountPoint,
    CloudDrive2UploadTask,
    CloudDrive2UploadWaiter,
    _map_mounted_path_to_cloud_path,
)


class FakeCloudDrive2Client:
    def __init__(self, task_pages):
        self.task_pages = list(task_pages)
        self.upload_calls = 0

    def list_mount_points(self):
        return [CloudDrive2MountPoint("D:\\", "/115open/tmp", is_mounted=True)]

    def list_upload_tasks(self):
        self.upload_calls += 1
        if self.task_pages:
            return self.task_pages.pop(0)
        return []


def _task(dest_path, status_enum=3, operator_type=0):
    return CloudDrive2UploadTask(
        key=dest_path,
        dest_path=dest_path,
        size=100,
        transferred_bytes=50 if status_enum == 3 else 100,
        status="",
        status_enum=status_enum,
        operator_type=operator_type,
    )


def test_maps_windows_mount_path_to_cloud_path():
    mapped = _map_mounted_path_to_cloud_path(
        Path("D:\\library\\Movie (2026)\\movie.nfo"),
        [CloudDrive2MountPoint("D:\\", "/115open/tmp", is_mounted=True)],
    )

    assert mapped == "/115open/tmp/library/Movie (2026)/movie.nfo"


def test_waiter_observes_mount_upload_until_finish(monkeypatch, mock_logger):
    monkeypatch.setattr("emby115_v2.services.clouddrive2.time.sleep", lambda _seconds: None)
    client = FakeCloudDrive2Client(
        [
            [_task("/115open/tmp/library/movie.nfo", status_enum=3)],
            [_task("/115open/tmp/library/movie.nfo", status_enum=5)],
        ]
    )
    waiter = CloudDrive2UploadWaiter(client, poll_interval_seconds=0.5, settle_seconds=0, max_wait_minutes=1)

    result = waiter.wait_for_paths([Path("D:\\library")], "run-1", mock_logger)

    assert result.status == "success"
    assert result.observed is True
    assert result.matched_count == 1
    assert client.upload_calls == 2


def test_waiter_treats_quiet_window_after_observed_as_success(monkeypatch, mock_logger):
    monkeypatch.setattr("emby115_v2.services.clouddrive2.time.sleep", lambda _seconds: None)
    client = FakeCloudDrive2Client(
        [
            [_task("/115open/tmp/library/movie.nfo", status_enum=0)],
            [],
        ]
    )
    waiter = CloudDrive2UploadWaiter(client, poll_interval_seconds=0.5, settle_seconds=0, max_wait_minutes=1)

    result = waiter.wait_for_paths([Path("D:\\library")], "run-1", mock_logger)

    assert result.status == "success"
    assert result.observed is True
    assert result.matched_count == 1
    assert "连续静默" in result.reason
    assert client.upload_calls == 2


def test_waiter_reports_not_observed_after_quiet_window(mock_logger):
    client = FakeCloudDrive2Client([[]])
    waiter = CloudDrive2UploadWaiter(client, poll_interval_seconds=0.5, settle_seconds=0, max_wait_minutes=1)

    result = waiter.wait_for_paths([Path("D:\\library")], "run-1", mock_logger)

    assert result.status == "not_observed"
    assert result.observed is False


def test_waiter_reports_upload_errors(mock_logger):
    client = FakeCloudDrive2Client([[_task("/115open/tmp/library/movie.nfo", status_enum=9)]])
    waiter = CloudDrive2UploadWaiter(client, poll_interval_seconds=0.5, settle_seconds=0, max_wait_minutes=1)

    result = waiter.wait_for_paths([Path("D:\\library")], "run-1", mock_logger)

    assert result.status == "failed"
    assert "上传任务失败" in result.reason
    assert result.error_count == 1
