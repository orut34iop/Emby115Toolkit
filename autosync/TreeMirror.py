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
    def __init__(self, tree_file: str, export_folder: str,fix_garbled = False, logger=None):
        self.tree_file = tree_file
        self.export_folder = export_folder
        self.fix_garbled = fix_garbled
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger

    def replace_special_chars(self,path: str) -> str:
        """
        替换路径中的特殊字符
        Args:
            path: 原始路径
        Returns:
            处理后的路径
        """
        if '*' in path:
            new_path = path.replace('*', 's')
            self.logger.info(f'Replace special chars: {path} -> {new_path}')
            return new_path
        return path

    def read_file_with_encodings(self,file_path: str) -> List[str]:
        """
        尝试使用不同的编码读取文件
        Args:
            file_path: 文件路径
        Returns:
            文件内容行列表
        Raises:
            UnicodeDecodeError: 当所有编码都无法正确读取文件时
        """
        encodings = ['utf-8', 'gbk', 'ansi', 'mbcs', 'gb2312']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.readlines()
            except UnicodeDecodeError:
                continue
        
        raise UnicodeDecodeError(f"无法使用以下编码读取文件: {encodings}")

    def parse_lines_to_tuples(self,file_path: str) -> List[Tuple[int, str]]:
        """
        解析文件内容为层级和名称的元组列表
        Args:
            file_path: 要解析的文件路径
        Returns:
            包含(层级,名称)元组的列表
        """
        tuples_list = []
        try:
            lines = self.read_file_with_encodings(file_path)
        except UnicodeDecodeError as e:
            self.logger.error(f"Error reading file: {e}")
            return []
        
        for line in lines:
            line = line.strip()
            if line.startswith('|——'):
                level = 1
                name = line[3:].strip()  # 修复拼写错误
            elif line.startswith('| |-'):
                level = 2
                name = line[4:].strip()
            elif line.startswith('| | |-'):
                level = 3
                name = line[6:].strip()
            elif line.startswith('| | | |-'):
                level = 4
                name = line[8:].strip()
            elif line.startswith('| | | | |-'):
                level = 5
                name = line[10:].strip()
            elif line.startswith('| | | | | |-'):
                level = 6
                name = line[12:].strip()
            elif line.startswith('| | | | | | |-'):
                level = 7
                name = line[14:].strip()
            elif line.startswith('| | | | | | | |-'):
                level = 8
                name = line[16:].strip()
            elif line.startswith('| | | | | | | | |-'):
                level = 9
                name = line[18:].strip()
            elif line.startswith('| | | | | | | | | |-'):
                level = 10
                name = line[20:].strip()
            else:
                continue
            tuples_list.append((level, name))
        
        return tuples_list

    def create_empty_files_from_list(self, file_path: str, tmp_dir: str, fix_garbled) -> None:
        """
        根据目录树文件创建空文件结构
        Args:
            file_path: 目录树文件路径
            tmp_dir: 输出目录路径
        """
        # 清空目录
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)
        
        file_items = self.parse_lines_to_tuples(file_path)
        current_dir = tmp_dir
        pre_level = 1  # init
        pre_item_type = ''  # init
        ignore_level = 0  # init
        for outer_index, item in enumerate(file_items):
            next_item_level = 0
            next_item_name = None
            level, name = item
            name = re.sub(r'[\\/*?:"<>|]', "_", name)
            if outer_index < len(file_items) - 1:
                next_item = file_items[outer_index + 1]
                next_item_level, next_item_name = next_item

            empty_file_path = ''  # RESET

            try:
                # 如果前面有异常错误的文件夹,跳过出错的目录下所有的子目录和文件
                if ignore_level > 0 and level > ignore_level: 
                    self.logger.info(f'ignore : {name}')
                    continue
                else:
                    ignore_level = 0

                if level == 1:
                    current_dir = os.path.join(tmp_dir, name)
                    if self.fix_garbled:
                        current_dir = self.replace_special_chars(current_dir)
                    pre_level = level
                    pre_item_type = 'dir'
                    os.makedirs(current_dir, exist_ok=True)
                else:
                    item_type = 'UNKNOWN'

                    # 下面这两者种情况都说明"演唱会.mp4"是文件夹
                    # | |-演唱会.mp4
                    # | | |-陈百强83演唱会.avi

                    # | |-演唱会.mp4
                    # | | |-演唱会
                    if re.match(r'.*\.[a-zA-Z0-9]{2,4}$', name):
                        if next_item_name and next_item_level > level:
                            self.logger.error(f'注意:识别为文件夹 {name}')
                            item_type = 'DIR'

                        '''
                        ########对于 pre_item_type == 'dir' 的情况
                        子一级  level == pre_level + 1
                        | | | |-folder1
                        | | | | |-folder2

                        同级    level == pre_level
                        | | | |-folder1
                        | | | |-folder2

                        上多级  level < pre_level
                        | | | |-folder1
                        | | |-folder2

                        ########对于 pre_item_type == 'file' 的情况
                        子一级  level == pre_level + 1
                        | | | |-file
                        | | | | |-folder
                        这种情况不可能出现, 错误退出

                        同级    level == pre_level
                        | | | |-file
                        | | | |-folder

                        上多级  level < pre_level
                        | | | |-file
                        | | |-folder
                        '''


                    if not re.match(r'.*\.[a-zA-Z0-9]{2,4}$', name) or item_type == 'DIR':  # 名称尾部不是'.xxx',表示2或者3或者4个数字或大小写字母,判定为目录
                        if pre_item_type == 'dir':  # 上一个是文件,回到上级目录
                            if level == pre_level + 1:  # 子目录
                                current_dir = os.path.join(current_dir, name)
                            elif level == pre_level:  # 同级目录
                                current_dir = os.path.dirname(current_dir)
                                current_dir = os.path.join(current_dir, name) 
                            elif level < pre_level:  # 上级目录
                                for _ in range(pre_level - level):
                                    current_dir = os.path.dirname(current_dir)
                                current_dir = os.path.join(os.path.dirname(current_dir), name)
                            else:  # 致命错误
                                self.logger.error(f'level error! pls check: {name}')
                                return
                        elif pre_item_type == 'file':  # 上一个操作的文件
                            if level == pre_level + 1:  # 子目录
                                self.logger.info(f'level error! pls check: {name}')
                                return
                            elif level == pre_level:  # 同级
                                current_dir = os.path.join(current_dir, name) 
                            elif level < pre_level:  # 上级目录
                                for _ in range(pre_level - level):
                                    current_dir = os.path.dirname(current_dir)
                                current_dir = os.path.join(current_dir, name)
                            else:  # 致命错误
                                self.logger.error(f'level error! pls check: {name}')
                                return
                        elif pre_item_type == '':  # 初始状态
                            pass
                        else:  # 致命错误
                            self.logger.error(f'level error! pls check: {name}')
                            return

                        try:
                            if self.fix_garbled:
                                current_dir = self.replace_special_chars(current_dir)
                            os.makedirs(current_dir, exist_ok=True)
                            pre_level = level
                            pre_item_type = 'dir'
                            self.logger.info(f'{pre_level} -- {level} dir  :  {current_dir}')
                        except Exception as e:
                            self.logger.error(f"Error creating directory: {e}")
                            ignore_level = level
                            return
                        
                    else:  # 文件
                        '''
                        ########对于 pre_item_type == 'dir' 的情况
                        子一级  level == pre_level + 1
                        | | | |-folder1
                        | | | | |-file

                        同级    level == pre_level
                        | | | |-folder1
                        | | | |-file

                        上多级  level < pre_level
                        | | | |-folder1
                        | | |-file

                        ########对于 pre_item_type == 'file' 的情况
                        子一级  level == pre_level + 1
                        | | | |-file1
                        | | | | |-file2
                        这种情况不可能出现, 错误退出

                        同级    level == pre_level
                        | | | |-file1
                        | | | |-file2

                        上多级  level < pre_level
                        | | | |-file1
                        | | |-file2
                        '''       
                        if pre_item_type == 'dir':  # 上一个是目录             
                            if level == pre_level + 1:  # 目录中的文件
                                empty_file_path = os.path.join(current_dir, name)
                            elif level == pre_level:  # 同级目录的文件
                                current_dir = os.path.dirname(current_dir)
                                empty_file_path = os.path.join(current_dir, name)
                            elif level < pre_level:  # 上级目录(可能多级)的文件 !!!!!!!!!!!需要测试检查 !!!!!!!!!!!
                                for _ in range(pre_level - level):
                                    current_dir = os.path.dirname(current_dir)
                                empty_file_path = os.path.join(current_dir, name)           
                            else:  # 致命错误
                                self.logger.error(f'level error! pls check: {name}')
                                return
                        elif pre_item_type == 'file':  # 上一个操作的文件      
                            if level == pre_level + 1:  # 不可能出现的情况
                                self.logger.error(f'level error! pls check: {name}')
                                return
                            elif level == pre_level:  # 同级目录的文件
                                empty_file_path = os.path.join(current_dir, name)
                            elif level < pre_level:  # 上级目录(可能多级)的文件 !!!!!!!!!!!需要测试检查 !!!!!!!!!!!
                                for _ in range(pre_level - level):
                                    current_dir = os.path.dirname(current_dir)
                                empty_file_path = os.path.join(current_dir, name)                         
                            else:  # 致命错误
                                self.logger.error(f'level error! pls check: {name}')
                                return
                        elif pre_item_type == '':
                            pass
                        else:  # 致命错误
                            self.logger.error(f'level error! pls check: {name}')
                            return

                        try:
                            if self.fix_garbled:
                                empty_file_path = self.replace_special_chars(empty_file_path)
                            open(empty_file_path, 'a').close()
                            pre_level = level
                            pre_item_type = 'file'
                            self.logger.info(f'{pre_level} -- {level} file :  {empty_file_path}')
                            continue
                        except Exception as e:
                            self.logger.error(f"Error creating file: {e}")
                            ignore_level = level
                            return
            except Exception as e:
                self.logger.error(f"Error processing {name}: {e}")
                current_dir = os.path.dirname(current_dir)  # 回到上一级目录
                self.logger.error(f'Error , set current_dir: {current_dir}')
                ignore_level = level
                return  # 异常直接退出
    
    def run(self):
        """
        运行同步处理
        """
        def run_in_thread():
            self.logger.info("开始生成文件镜像...")
            match_count = 0
            move_count = 0
            start_time = time.time()
            self.create_empty_files_from_list(self.tree_file, self.export_folder, self.fix_garbled)
            end_time = time.time()
            total_time = end_time - start_time
            message = f"生成文件镜像完成{self.export_folder}:总耗时 {total_time:.2f} 秒"
            self.logger.info(message)
            return

        thread = threading.Thread(target=run_in_thread)
        thread.start()