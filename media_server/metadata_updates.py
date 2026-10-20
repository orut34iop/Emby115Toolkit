"""Bounded candidate processing; callbacks and result accounting stay on one thread."""

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def update_candidates(client, candidates, field, translate, label, callback):
    total = len(candidates)
    if not total:
        return []
    # Local snapshots avoid a second HTTP read and use a verified local server.
    # Keep remote servers at the more conservative limit.
    workers = 8 if client._local_catalog is not None else 4
    indexed = iter(enumerate(candidates))
    pending, results = {}, {}
    processed = unchanged = failed = 0
    started = last_report = time.monotonic()
    last_count = 0

    def update(candidate):
        if client.stop_flag.is_set():
            return 'cancelled', None
        identifier = candidate['Id']
        current = client.get_item_info(identifier)
        if not current or current.get('Id') != identifier:
            raise ValueError('无法读取当前条目')
        if candidate.get('_local_snapshot') and (
            current.get('Path') != candidate.get('Path') or current.get('Type') != candidate.get('Type')
        ):
            raise ValueError('条目路径或类型已改变，请重新扫描')
        original = current.get(field, [])
        if not isinstance(original, list) or any(not isinstance(value, str) for value in original):
            raise ValueError('当前字段值格式无效')
        translated = translate(original)
        if original == translated:
            return 'unchanged', None
        if client.stop_flag.is_set():
            return 'cancelled', None
        current[field] = translated
        response = client._save_curated_field(identifier, current, field)
        if response.status_code not in (200, 204):
            raise ValueError(f"保存或校验失败（{response.status_code}）: {response.text}")
        return 'updated', current

    def report(force=False):
        nonlocal last_report, last_count
        now = time.monotonic()
        if not force and processed - last_count < 100 and now - last_report < 5:
            return
        last_report, last_count = now, processed
        speed = processed / max(now - started, 0.001)
        client._report_progress(
            callback, processed, total,
            f"更新{label}进度: {processed}/{total}，已成功 {len(results)}，"
            f"无需变更 {unchanged}，失败 {failed}，{speed:.1f} 条/秒",
            percent=client._progress_percent(processed, total, 50, 50),
        )

    report(force=True)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='metadata-update') as executor:
        exhausted = False
        while pending or not exhausted:
            while not exhausted and not client.stop_flag.is_set() and len(pending) < workers:
                entry = next(indexed, None)
                if entry is None:
                    exhausted = True
                    break
                index, candidate = entry
                pending[executor.submit(update, candidate)] = (index, candidate)
            if client.stop_flag.is_set():
                exhausted = True
            if not pending:
                break
            done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for future in done:
                index, candidate = pending.pop(future)
                try:
                    status, item = future.result()
                    if status == 'updated':
                        results[index] = item
                    elif status == 'unchanged':
                        unchanged += 1
                    else:
                        continue
                except Exception as error:
                    failed += 1
                    client._mark_metadata_error()
                    client.logger.error(f"{label}条目 {candidate['Id']} 处理失败: {error}")
                processed += 1
            report()
    report(force=True)
    client.logger.info(
        f"{label}{'已停止' if client.stop_flag.is_set() else '处理结束'}："
        f"已处理 {processed}/{total}，成功 {len(results)}，无需变更 {unchanged}，失败 {failed}"
    )
    return [results[index] for index in sorted(results)]
