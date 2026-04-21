import os
import os
import time
import threading
import logging
import shutil
import re
from typing import List, Tuple
from utils.logger import setup_logger
from utils.listdir import list_files

class TreeMirror:
    def __init__(self, tree_file: str, export_folder: str, fix_garbled=False, fix_garbled_text=False, logger=None):
        """
        初始化 TreeMirror
        :param tree_file: 目录树文件路径
        :param export_folder: 导出文件夹路径
        :param fix_garbled: 修复乱码（兼容旧参数名）
        :param fix_garbled_text: 修复乱码（测试使用的参数名）
        :param logger: 日志记录器
        """
        self.tree_file = tree_file
        self.export_folder = export_folder
        self.fix_garbled = fix_garbled or fix_garbled_text
        self.fix_garbled_text = self.fix_garbled  # 兼容测试使用的属性名
        self.logger = logger or logging.getLogger(__name__)
        
        # 停止标志
        self.stop_flag = threading.Event()

    def replace_special_chars(self, path: str) -> str:
        """
        替换路径中的特殊字符
        """
        if '*' in path:
            new_path = path.replace('*', 's')
            self.logger.info(f'Replace special chars: {path} -> {new_path}')
            return new_path
        return path

    def read_file_with_encodings(self, file_path: str) -> List[str]:
        """
        尝试使用不同的编码读取文件
        """
        encodings = ['utf-8', 'gbk', 'cp1252', 'mbcs', 'gb2312', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.readlines()
            except UnicodeDecodeError:
                continue
        
        self.logger.error(f"无法使用以下编码读取文件: {encodings}")
        raise UnicodeDecodeError("read_file_with_encodings", file_path, 0, 0, "无法使用以下编码读取文件")

    def parse_tree(self) -> list:
        """
        解析目录树文件，返回结构列表
        :return: 包含 name, is_dir, depth 的字典列表
        """
        result = []
        
        if not os.path.exists(self.tree_file):
            return result
        
        try:
            lines = self.read_file_with_encodings(self.tree_file)
        except UnicodeDecodeError:
            return result
        
        # 先收集所有原始条目
        raw_items = []
        for line in lines:
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue
            
            # 解析层级
            depth = 0
            name = line.strip()
            
            if line.startswith('|——'):
                depth = 1
                name = line[3:].strip()
            elif line.startswith('| |-'):
                depth = 2
                name = line[4:].strip()
            elif line.startswith('| | |-'):
                depth = 3
                name = line[6:].strip()
            elif line.startswith('| | | |-'):
                depth = 4
                name = line[8:].strip()
            elif line.startswith('| | | | |-'):
                depth = 5
                name = line[10:].strip()
            elif line.startswith('| | | | | |-'):
                depth = 6
                name = line[12:].strip()
            elif line.startswith('| | | | | | |-'):
                depth = 7
                name = line[14:].strip()
            elif line.startswith('| | | | | | | |-'):
                depth = 8
                name = line[16:].strip()
            elif line.startswith('| | | | | | | | |-'):
                depth = 9
                name = line[18:].strip()
            elif line.startswith('| | | | | | | | | |-'):
                depth = 10
                name = line[20:].strip()
            else:
                depth = 0
                name = line.strip()
            
            if not name:
                continue
            
            # 修复乱码
            if self.fix_garbled and '*' in name:
                name = name.replace('*', 's')
            
            raw_items.append({'name': name, 'depth': depth})
        
        # 二次遍历：如果某个条目后面有更深层的条目，则它是目录
        for i, item in enumerate(raw_items):
            name = item['name']
            depth = item['depth']
            
            # 检查是否有子项
            has_children = False
            if i < len(raw_items) - 1:
                next_depth = raw_items[i + 1]['depth']
                if next_depth > depth:
                    has_children = True
            
            # 如果有子项，一定是目录；否则根据扩展名判断
            is_dir = has_children or not re.match(r'.*\.[a-zA-Z0-9]{2,4}$', name)
            
            result.append({
                'name': name,
                'is_dir': is_dir,
                'depth': depth
            })
        
        return result

    def create_structure(self, tree_data: list, callback=None) -> None:
        """
        根据解析的树数据创建目录结构
        :param tree_data: parse_tree 返回的数据
        :param callback: 回调函数
        """
        def send_message(msg):
            self.logger.info(msg)
            if callback:
                callback(msg)
        
        if not tree_data:
            send_message("树数据为空")
            return
        
        os.makedirs(self.export_folder, exist_ok=True)
        
        # 使用栈来跟踪当前路径
        path_stack = [self.export_folder]
        
        # 如果第一个条目是根目录（depth=0），跳过它，其子项直接放在 export_folder 下
        start_index = 0
        if tree_data and tree_data[0]['depth'] == 0:
            start_index = 1
        
        for i, item in enumerate(tree_data):
            if i < start_index:
                continue
                
            if self.stop_flag.is_set():
                send_message("操作已停止")
                return
            
            name = item['name']
            depth = item['depth']
            is_dir = item['is_dir']
            
            # 清理名称
            name = re.sub(r'[\\/*?:"<>|]', "_", name)
            name = name.strip('.')
            if '..' in name:
                name = name.replace('..', '_')
            
            # 调整路径栈到正确的深度
            # 如果跳过了根目录，depth 需要相应调整
            adjusted_depth = depth - start_index
            while len(path_stack) > adjusted_depth + 1:
                path_stack.pop()
            
            # 构建完整路径
            current_path = os.path.join(path_stack[-1], name)
            
            if is_dir:
                os.makedirs(current_path, exist_ok=True)
                send_message(f"创建目录: {current_path}")
                # 确保栈中有当前目录
                if len(path_stack) <= adjusted_depth + 1:
                    path_stack.append(current_path)
                else:
                    path_stack[adjusted_depth + 1] = current_path
            else:
                # 创建空文件（如果不存在）
                if not os.path.exists(current_path):
                    with open(current_path, 'a'):
                        pass
                    send_message(f"创建文件: {current_path}")
                else:
                    send_message(f"文件已存在，跳过: {current_path}")

    def run(self, callback=None):
        """
        运行完整的镜像创建流程
        :param callback: 回调函数
        """
        def send_message(msg):
            self.logger.info(msg)
            if callback:
                callback(msg)
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        send_message(f"开始解析目录树文件: {self.tree_file}")
        tree_data = self.parse_tree()
        send_message(f"解析完成，共 {len(tree_data)} 个项目")
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        send_message(f"开始创建目录结构到: {self.export_folder}")
        self.create_structure(tree_data, callback)
        send_message("目录树镜像创建完成")

    # ========== 兼容旧版接口 ==========
    
    def parse_lines_to_tuples(self, file_path: str) -> List[Tuple[int, str]]:
        """兼容旧接口"""
        result = []
        data = self.parse_tree()
        for item in data:
            result.append((item['depth'], item['name']))
        return result

    def create_empty_files_from_list(self, file_path: str, tmp_dir: str, fix_garbled) -> None:
        """兼容旧接口"""
        self.export_folder = tmp_dir
        self.fix_garbled = fix_garbled
        tree_data = self.parse_tree()
        self.create_structure(tree_data)
