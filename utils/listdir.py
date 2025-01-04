import os
import time
from pathlib import Path
import logging
from utils.logger import setup_logger

def generate_output_filename(folder_path: str) -> str:
    """
    根据输入文件夹生成唯一的输出文件名
    :param folder_path: 输入文件夹路径
    :return: 输出文件名
    """
    # 获取文件夹名称
    folder_name = os.path.basename(folder_path.rstrip('/\\'))
    # 添加时间戳避免重复
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    return f"{folder_name}_files_{timestamp}.txt"

def list_files(folder_path: str, enable_115_protect: bool, op_interval_sec: int, output_path = "", is_first_call = True, logger = None) -> tuple[int, list[str], str]:

    list_files_logger = logger or logging.getLogger(__name__)  # 使用传递的logger
    """
    遍历文件夹，获取所有文件的绝对路径并保存到文本文件
    :param folder_path: 要遍历的文件夹路径
    :param enable_115_protect: 是否启用115防封
    :param op_interval_sec: 操作间隔时间（秒）
    :param output_path: 输出文件路径
    :param is_first_call: 是否是第一次调用
    :param logger: 日志记录器
    :return: (文件数量, 文件路径列表, 输出文件路径)
    """
    if is_first_call:
        list_files_logger.info("list_files : This is the first call.")
        # 生成输出文件名
        output_filename = generate_output_filename(folder_path)
        
        # 在当前工作目录下创建mergeLog目录
        output_dir = os.path.join(os.getcwd(), "mergeLog")
        os.makedirs(output_dir, exist_ok=True)
        
        # 完整的输出文件路径
        output_path = os.path.join(output_dir, output_filename)
        # 删除同名文件
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as e:
                list_files_logger.error(f"无法删除文件 {output_path}: {e}")
    else:
        if enable_115_protect:
            list_files_logger.info("list_files 115防封已启用")
            time.sleep(int(op_interval_sec))

        list_files_logger.info("list_files : This is sub call.")
        list_files_logger.info(f"folder_path: {folder_path}")

    try:
        # 确保文件夹路径存在
        if not os.path.exists(folder_path):
            list_files_logger.error(f"文件夹不存在: {folder_path}")
            return 0, [], ""

        file_paths = []
        for entry in os.scandir(folder_path):
            if entry.is_file():
                abs_path = entry.path
                file_paths.append(abs_path)
                list_files_logger.debug(f"找到文件: {abs_path}")
            elif entry.is_dir():
                # 递归调用list_files处理子目录
                sub_folder_count, sub_folder_files, _ = list_files(entry.path, enable_115_protect, op_interval_sec, is_first_call=False, logger=list_files_logger)
                file_paths.extend(sub_folder_files)

        if not file_paths:
            list_files_logger.info(f"文件夹为空: {folder_path}")
            return 0, [], ""

        file_count = len(file_paths)

        if is_first_call:
            # 退出递归时,写入文件
            with open(output_path, 'a', encoding='utf-8') as f:
                if file_paths:
                    for file_path in file_paths:
                        f.write(f"{file_path}\n")
            list_files_logger.info(f"已保存文件列表到: {output_path}")
            list_files_logger.info(f"找到 {file_count} 个文件")

        return file_count, file_paths, str(output_path)

    except Exception as e:
        list_files_logger.error(f"遍历文件夹时出错: {str(e)}")
        return 0, [], ""

def get_file_count(folder_path: str) -> int:
    """
    获取文件夹中的文件总数
    :param folder_path: 文件夹路径
    :return: 文件总数
    """
    try:
        count = sum(len(files) for _, _, files in os.walk(folder_path))
        return count
    except Exception as e:
        #logging.error(f"获取文件数量时出错: {str(e)}")
        return 0
