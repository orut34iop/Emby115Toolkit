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

def list_files(folder_path: str) -> tuple[list[str], str]:
    """
    遍历文件夹，获取所有文件的绝对路径并保存到文本文件
    :param folder_path: 要遍历的文件夹路径
    :return: (文件数量, 文件路径列表, 输出文件路径)
    """
    try:
        # 确保文件夹路径存在
        if not os.path.exists(folder_path):
            logging.error(f"文件夹不存在: {folder_path}")
            return 0, [], ""

        # 获取所有文件的绝对路径
        file_paths = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.abspath(os.path.join(root, file))
                file_paths.append(abs_path)
                logging.debug(f"找到文件: {abs_path}")

        if not file_paths:
            logging.warning(f"文件夹为空: {folder_path}")
            return 0, [], ""

        # 生成输出文件名
        output_filename = generate_output_filename(folder_path)
        
        # 在当前工作目录下创建mergeLog目录
        output_dir = os.path.join(os.getcwd(), "mergeLog")
        os.makedirs(output_dir, exist_ok=True)
        
        # 完整的输出文件路径
        output_path = os.path.join(output_dir, output_filename)

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for file_path in file_paths:
                f.write(f"{file_path}\n")

        file_count = len(file_paths)
        logging.info(f"已保存文件列表到: {output_path}")
        logging.info(f"共找到 {file_count} 个文件")

        return file_count, file_paths, output_path

    except Exception as e:
        logging.error(f"遍历文件夹时出错: {str(e)}")
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
        logging.error(f"获取文件数量时出错: {str(e)}")
        return 0
