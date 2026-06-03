from __future__ import annotations

import logging
import ntpath
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from emby115_v2 import cancellation
from emby115_v2.context import AppContext


MOUNT_OPERATOR_TYPE = 0
ACTIVE_UPLOAD_STATUSES = {0, 1, 3, 4, 7}
ERROR_UPLOAD_STATUSES = {2, 9, 10}
TERMINAL_UPLOAD_STATUSES = {5, 6, 8}
UPLOAD_STATUS_NAMES = {
    0: "WaitforPreprocessing",
    1: "Preprocessing",
    2: "Cancelled",
    3: "Transfer",
    4: "Pause",
    5: "Finish",
    6: "Skipped",
    7: "Inqueue",
    8: "Ignored",
    9: "Error",
    10: "FatalError",
}


@dataclass(frozen=True)
class CloudDrive2MountPoint:
    mount_point: str
    source_dir: str
    local_mount: bool = False
    is_mounted: bool = False
    name: str = ""


@dataclass(frozen=True)
class CloudDrive2UploadTask:
    key: str
    dest_path: str
    size: int
    transferred_bytes: int
    status: str
    status_enum: int
    operator_type: int
    error_message: str = ""

    @property
    def status_name(self) -> str:
        return UPLOAD_STATUS_NAMES.get(self.status_enum, self.status or str(self.status_enum))

    @property
    def is_active(self) -> bool:
        return self.status_enum in ACTIVE_UPLOAD_STATUSES

    @property
    def is_error(self) -> bool:
        return self.status_enum in ERROR_UPLOAD_STATUSES

    @property
    def is_terminal_success(self) -> bool:
        return self.status_enum in TERMINAL_UPLOAD_STATUSES


@dataclass(frozen=True)
class CloudDrive2WaitResult:
    status: str
    reason: str
    observed: bool = False
    waited_seconds: float = 0.0
    watched_roots: tuple[str, ...] = ()
    active_count: int = 0
    error_count: int = 0
    matched_count: int = 0
    matched_tasks: tuple[CloudDrive2UploadTask, ...] = field(default_factory=tuple)


class CloudDrive2ClientProtocol:
    def list_mount_points(self) -> list[CloudDrive2MountPoint]:
        raise NotImplementedError

    def list_upload_tasks(self) -> list[CloudDrive2UploadTask]:
        raise NotImplementedError


class CloudDrive2GrpcClient(CloudDrive2ClientProtocol):
    """Minimal CloudDrive2 gRPC client for upload task observation.

    The project only needs a small subset of the official proto. To avoid
    vendoring generated files, this client builds compatible protobuf message
    types lazily at runtime and calls the gRPC methods directly.
    """

    def __init__(
        self,
        endpoint: str = "127.0.0.1:19798",
        api_token: str = "",
        timeout: float = 10.0,
        page_size: int = 100,
        max_pages: int = 50,
    ):
        self.endpoint = _normalize_grpc_endpoint(endpoint)
        self.api_token = api_token
        self.timeout = max(1.0, float(timeout))
        self.page_size = max(1, int(page_size))
        self.max_pages = max(1, int(max_pages))
        self._channel: Any | None = None
        self._messages: dict[str, Any] | None = None

    @classmethod
    def from_context(cls, context: AppContext) -> "CloudDrive2GrpcClient":
        return cls(
            endpoint=context.clouddrive2.endpoint,
            api_token=context.clouddrive2.api_token,
            timeout=context.clouddrive2.timeout,
            page_size=context.clouddrive2.page_size,
            max_pages=context.clouddrive2.max_pages,
        )

    def list_mount_points(self) -> list[CloudDrive2MountPoint]:
        messages = self._get_messages()
        stub = self._channel.unary_unary(
            "/clouddrive.CloudDriveFileSrv/GetMountPoints",
            request_serializer=messages["Empty"].SerializeToString,
            response_deserializer=messages["GetMountPointsResult"].FromString,
        )
        response = stub(messages["Empty"](), metadata=self._metadata(), timeout=self.timeout)
        return [
            CloudDrive2MountPoint(
                mount_point=str(item.mountPoint),
                source_dir=str(item.sourceDir),
                local_mount=bool(item.localMount),
                is_mounted=bool(item.isMounted),
                name=str(item.name),
            )
            for item in response.mountPoints
        ]

    def list_upload_tasks(self) -> list[CloudDrive2UploadTask]:
        messages = self._get_messages()
        stub = self._channel.unary_unary(
            "/clouddrive.CloudDriveFileSrv/GetUploadFileList",
            request_serializer=messages["GetUploadFileListRequest"].SerializeToString,
            response_deserializer=messages["GetUploadFileListResult"].FromString,
        )
        tasks: list[CloudDrive2UploadTask] = []
        for page in range(self.max_pages):
            request = messages["GetUploadFileListRequest"](
                getAll=False,
                itemsPerPage=self.page_size,
                pageNumber=page,
                filter="",
            )
            response = stub(request, metadata=self._metadata(), timeout=self.timeout)
            tasks.extend(_upload_task_from_proto(item) for item in response.uploadFiles)
            if not response.uploadFiles or len(tasks) >= int(response.totalCount or 0):
                break
        return tasks

    def _metadata(self) -> list[tuple[str, str]]:
        if not self.api_token:
            return []
        return [("authorization", f"Bearer {self.api_token}")]

    def _get_messages(self) -> dict[str, Any]:
        if self._messages is not None:
            return self._messages
        try:
            import grpc
            from google.protobuf import descriptor_pb2, descriptor_pool, empty_pb2, message_factory
        except ImportError as exc:
            raise RuntimeError(
                "使用 CloudDrive2 gRPC 上传任务探测需要安装 grpcio 和 protobuf，请先执行 pip install -r requirements.txt"
            ) from exc

        pool = descriptor_pool.DescriptorPool()
        file_proto = descriptor_pb2.FileDescriptorProto()
        file_proto.name = "emby115_clouddrive2_minimal.proto"
        file_proto.package = "clouddrive"
        file_proto.syntax = "proto3"

        _add_message(
            file_proto,
            "MountPoint",
            [
                ("mountPoint", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("sourceDir", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("localMount", 3, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                ("readOnly", 4, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                ("autoMount", 5, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                ("isMounted", 9, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                ("failReason", 10, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("name", 11, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
            ],
        )
        _add_message(
            file_proto,
            "GetMountPointsResult",
            [
                (
                    "mountPoints",
                    1,
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ".clouddrive.MountPoint",
                )
            ],
        )
        _add_message(
            file_proto,
            "UploadFileInfo",
            [
                ("key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("destPath", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("size", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT64),
                ("transferedBytes", 4, descriptor_pb2.FieldDescriptorProto.TYPE_UINT64),
                ("status", 5, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("errorMessage", 6, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ("operatorType", 7, descriptor_pb2.FieldDescriptorProto.TYPE_INT32),
                ("statusEnum", 8, descriptor_pb2.FieldDescriptorProto.TYPE_INT32),
            ],
        )
        _add_message(
            file_proto,
            "GetUploadFileListRequest",
            [
                ("getAll", 1, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                ("itemsPerPage", 2, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32),
                ("pageNumber", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32),
                ("filter", 4, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
            ],
        )
        _add_message(
            file_proto,
            "GetUploadFileListResult",
            [
                ("totalCount", 1, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32),
                (
                    "uploadFiles",
                    2,
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ".clouddrive.UploadFileInfo",
                ),
                ("globalBytesPerSecond", 3, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE),
                ("totalBytes", 4, descriptor_pb2.FieldDescriptorProto.TYPE_UINT64),
                ("finishedBytes", 5, descriptor_pb2.FieldDescriptorProto.TYPE_UINT64),
            ],
        )
        pool.Add(file_proto)
        self._messages = {
            "Empty": empty_pb2.Empty,
            "GetMountPointsResult": message_factory.GetMessageClass(
                pool.FindMessageTypeByName("clouddrive.GetMountPointsResult")
            ),
            "GetUploadFileListRequest": message_factory.GetMessageClass(
                pool.FindMessageTypeByName("clouddrive.GetUploadFileListRequest")
            ),
            "GetUploadFileListResult": message_factory.GetMessageClass(
                pool.FindMessageTypeByName("clouddrive.GetUploadFileListResult")
            ),
        }
        self._channel = grpc.insecure_channel(self.endpoint)
        return self._messages


class CloudDrive2UploadWaiter:
    def __init__(
        self,
        client: CloudDrive2ClientProtocol,
        poll_interval_seconds: float = 0.5,
        settle_seconds: float = 30.0,
        max_wait_minutes: int = 60,
    ):
        self.client = client
        self.poll_interval_seconds = max(0.5, float(poll_interval_seconds))
        self.settle_seconds = max(0.0, float(settle_seconds))
        self.max_wait_seconds = max(0.0, float(max_wait_minutes) * 60.0)

    @classmethod
    def from_context(cls, context: AppContext, client: CloudDrive2ClientProtocol | None = None) -> "CloudDrive2UploadWaiter":
        return cls(
            client or CloudDrive2GrpcClient.from_context(context),
            poll_interval_seconds=context.clouddrive2.poll_interval_seconds,
            settle_seconds=context.clouddrive2.settle_seconds,
            max_wait_minutes=context.clouddrive2.max_wait_minutes,
        )

    def wait_for_paths(
        self,
        paths: list[Path],
        run_id: str,
        logger: logging.Logger,
    ) -> CloudDrive2WaitResult:
        started = time.monotonic()
        try:
            mount_points = self.client.list_mount_points()
        except Exception as exc:
            return CloudDrive2WaitResult("failed", f"无法读取 CloudDrive2 挂载点: {exc}")

        watched_roots = tuple(_watched_roots_for_paths(paths, mount_points))
        if not watched_roots:
            return CloudDrive2WaitResult("failed", "无法从目标路径推导 CloudDrive2 上传任务匹配路径")

        logger.info("CloudDrive2 上传等待开始，监控路径: %s", ", ".join(watched_roots))
        deadline = started + self.max_wait_seconds if self.max_wait_seconds > 0 else started
        observed = False
        first_observed_at: float | None = None
        last_no_match_at: float | None = None
        last_tasks: tuple[CloudDrive2UploadTask, ...] = ()

        while True:
            if cancellation.is_cancelled(run_id):
                return CloudDrive2WaitResult(
                    "canceled",
                    "等待 CloudDrive2 上传任务期间收到取消请求",
                    observed=observed,
                    waited_seconds=time.monotonic() - started,
                    watched_roots=watched_roots,
                    matched_tasks=last_tasks,
                )
            now = time.monotonic()
            if self.max_wait_seconds > 0 and now >= deadline:
                return CloudDrive2WaitResult(
                    "timeout",
                    "等待 CloudDrive2 上传任务完成超时",
                    observed=observed,
                    waited_seconds=now - started,
                    watched_roots=watched_roots,
                    matched_tasks=last_tasks,
                )

            try:
                tasks = self.client.list_upload_tasks()
            except Exception as exc:
                return CloudDrive2WaitResult(
                    "failed",
                    f"无法读取 CloudDrive2 上传任务: {exc}",
                    observed=observed,
                    waited_seconds=now - started,
                    watched_roots=watched_roots,
                    matched_tasks=last_tasks,
                )

            matched = tuple(
                task
                for task in tasks
                if task.operator_type == MOUNT_OPERATOR_TYPE and _path_matches_any_root(task.dest_path, watched_roots)
            )
            active = tuple(task for task in matched if task.is_active)
            errors = tuple(task for task in matched if task.is_error)
            terminal_success = tuple(task for task in matched if task.is_terminal_success)
            if matched:
                last_tasks = matched
                observed = True
                if first_observed_at is None:
                    first_observed_at = now
                    logger.info("已观测到匹配的 CloudDrive2 挂载上传任务，进入已开始上传状态")
                last_no_match_at = None

            if errors:
                reason = "; ".join(
                    f"{task.dest_path} {task.status_name} {task.error_message}".strip() for task in errors[:5]
                )
                return CloudDrive2WaitResult(
                    "failed",
                    f"CloudDrive2 上传任务失败: {reason}",
                    observed=observed,
                    waited_seconds=now - started,
                    watched_roots=watched_roots,
                    active_count=len(active),
                    error_count=len(errors),
                    matched_count=len(matched),
                    matched_tasks=matched,
                )

            if active:
                total_size = sum(task.size for task in active)
                transferred = sum(task.transferred_bytes for task in active)
                logger.info(
                    "CloudDrive2 上传中 active=%s transferred=%s/%s 示例=%s",
                    len(active),
                    transferred,
                    total_size,
                    active[0].dest_path,
                )
            elif terminal_success:
                return CloudDrive2WaitResult(
                    "success",
                    "CloudDrive2 挂载盘上传任务已全部进入完成状态",
                    observed=True,
                    waited_seconds=now - started,
                    watched_roots=watched_roots,
                    matched_count=len(matched),
                    matched_tasks=matched,
                )
            else:
                if last_no_match_at is None:
                    last_no_match_at = now
                quiet_seconds = now - last_no_match_at
                if observed:
                    logger.info(
                        "已观测到上传任务，当前无匹配任务，连续静默 %.1f/%s 秒",
                        quiet_seconds,
                        self.settle_seconds,
                    )
                else:
                    logger.info("尚未观测到匹配的 CloudDrive2 挂载上传任务，已等待 %.1f 秒", quiet_seconds)
                if quiet_seconds >= self.settle_seconds and observed:
                    return CloudDrive2WaitResult(
                        "success",
                        "已观测到 CloudDrive2 上传任务，随后连续静默窗口内无匹配任务，视为上传结束",
                        observed=True,
                        waited_seconds=now - started,
                        watched_roots=watched_roots,
                        matched_count=len(last_tasks),
                        matched_tasks=last_tasks,
                    )
                if quiet_seconds >= self.settle_seconds:
                    return CloudDrive2WaitResult(
                        "not_observed",
                        "在静默窗口内没有观测到匹配的 CloudDrive2 挂载上传任务",
                        observed=False,
                        waited_seconds=now - started,
                        watched_roots=watched_roots,
                    )

            time.sleep(min(self.poll_interval_seconds, max(0.1, deadline - time.monotonic()) if self.max_wait_seconds else self.poll_interval_seconds))


def _add_message(file_proto: Any, name: str, fields: list[tuple[Any, ...]]) -> None:
    from google.protobuf import descriptor_pb2

    message = file_proto.message_type.add()
    message.name = name
    for field_info in fields:
        field = message.field.add()
        field.name = field_info[0]
        field.number = field_info[1]
        field.type = field_info[2]
        field.label = (
            field_info[3]
            if len(field_info) >= 4
            else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        )
        if len(field_info) >= 5:
            field.type_name = field_info[4]


def _upload_task_from_proto(item: Any) -> CloudDrive2UploadTask:
    return CloudDrive2UploadTask(
        key=str(item.key),
        dest_path=str(item.destPath),
        size=int(item.size),
        transferred_bytes=int(item.transferedBytes),
        status=str(item.status),
        error_message=str(item.errorMessage),
        operator_type=int(item.operatorType),
        status_enum=int(item.statusEnum),
    )


def _normalize_grpc_endpoint(endpoint: str) -> str:
    value = (endpoint or "127.0.0.1:19798").strip()
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    return value


def _watched_roots_for_paths(paths: list[Path], mount_points: list[CloudDrive2MountPoint]) -> list[str]:
    roots: list[str] = []
    for path in paths:
        raw = _normalize_match_path(str(path))
        if raw:
            roots.append(raw)
        mapped = _map_mounted_path_to_cloud_path(path, mount_points)
        if mapped:
            roots.append(_normalize_match_path(mapped))
    return sorted({root for root in roots if root})


def _map_mounted_path_to_cloud_path(path: Path, mount_points: list[CloudDrive2MountPoint]) -> str:
    local_path = str(path)
    local_norm = _normalize_windows_path(local_path)
    for mount in mount_points:
        if not mount.is_mounted:
            continue
        mount_norm = _normalize_windows_path(mount.mount_point)
        if not mount_norm:
            continue
        if local_norm == mount_norm:
            relative = ""
        elif local_norm.startswith(mount_norm + "\\"):
            relative = local_path[len(_ensure_windows_root(mount.mount_point)) :].lstrip("\\/")
        else:
            continue
        source_root = _normalize_match_path(mount.source_dir)
        relative_cloud = relative.replace("\\", "/").strip("/")
        return f"{source_root}/{relative_cloud}" if relative_cloud else source_root
    return ""


def _normalize_windows_path(value: str) -> str:
    normalized = _ensure_windows_root(value).replace("/", "\\")
    return normalized.rstrip("\\").casefold()


def _ensure_windows_root(value: str) -> str:
    result = str(value).strip().replace("/", "\\")
    if len(result) == 2 and result[1] == ":":
        result += "\\"
    return result


def _normalize_match_path(value: str) -> str:
    result = str(value).strip().replace("\\", "/")
    while "//" in result:
        result = result.replace("//", "/")
    drive, tail = ntpath.splitdrive(result)
    if drive:
        result = drive.upper() + tail
    return result.rstrip("/").casefold()


def _path_matches_any_root(path: str, roots: tuple[str, ...]) -> bool:
    normalized = _normalize_match_path(path)
    return any(normalized == root or normalized.startswith(root + "/") for root in roots)
