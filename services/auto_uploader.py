import os
import time

import yaml

from services.metadata_copier import MetadataCopier
from utils.service_messages import print_message

working_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(working_directory)

try:
    from create_config import create_config

    if not os.path.exists('./config/config_done.txt'):
        create_config()
except ImportError:
    pass


class AutoUploader:
    def __init__(self, config_path='./config/config.yaml'):
        self.config_path = config_path
        self.metadata_ext = (".nfo", ".jpg", ".png", ".svg", ".ass", ".srt", ".sup")

    def read_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            return data
        except Exception as e:
            print_message(f"不存在配置文件,请创建配置文件: {e}")
            return None

    def calculate_sync_interval(self, input_str):
        try:
            expression = str(input_str).strip()
            factors = [factor.strip() for factor in expression.split('*')]
            if not factors or any(not factor.isdigit() for factor in factors):
                raise ValueError(f"无效的同步间隔表达式: {input_str}")

            result = 1
            for factor in factors:
                result *= int(factor)
            return result
        except (TypeError, ValueError) as e:
            print_message(f"Error: {e}")
            return 86400

    def parse_extensions(self, extensions_str):
        # 去掉前后的空格,并使用分号分隔
        extensions_list = extensions_str.strip().split(';')
        # 去掉空的元素
        extensions_list = [ext.strip() for ext in extensions_list if ext.strip()]
        # 返回一个元组
        return tuple(extensions_list)

    def run(self):
        yaml_data = self.read_config()
        if not yaml_data:
            return
        upload_enabled = yaml_data.get('upload_enabled', True)
        if not upload_enabled:
            print_message('当前并未开启上传状态,如需开启,请至config.yaml中将upload_enabled设为true')
            return

        upload_scheduled = yaml_data.get('upload_scheduled', False)
        if upload_scheduled:
            while True:
                # 等待指定秒数
                upload_sync_time = self.calculate_sync_interval(yaml_data.get('upload_sync_time', False))
                self.run_once()
                time.sleep(upload_sync_time)
        else:
            self.run_once()

    def run_once(self):
        total_time = 0
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print_message(f"程序运行开始时间: {current_time}")
        yaml_data = self.read_config()
        if not yaml_data:
            return
        upload_list = yaml_data.get('upload_list', [])
        thread_count = yaml_data.get('thread_count', yaml_data.get('num_threads', 8))
        self.metadata_ext = yaml_data.get('metadata_ext', '.nfo;.jpg;.png;.svg;.ass;.srt;.sup')
        for dir_dict in upload_list:
            source_dir = dir_dict.get('source_dir')
            target_dir = dir_dict.get('target_dir')
            upload_enabled = dir_dict.get('upload_enabled', False)
            metadata_ext = self.parse_extensions(dir_dict.get('metadata_ext', self.metadata_ext))
            if upload_enabled:
                metadata_copier = MetadataCopier(
                    source_folders=[source_dir],
                    target_folder=target_dir,
                    allowed_extensions=metadata_ext,
                    thread_count=thread_count,
                )
                copy_start_time = time.time()
                copy_result = metadata_copier.run(lambda message: print_message(message))
                if hasattr(copy_result, "join"):
                    copy_result.join()
                    total_time += time.time() - copy_start_time
                elif isinstance(copy_result, (int, float)):
                    total_time += copy_result
                print_message(f'上传完成,共耗时{total_time:.2f}秒.')


if __name__ == '__main__':
    auto_uploader = AutoUploader()
    auto_uploader.run()
    # while True:
    #     auto_uploader.run()
    #     time.sleep(999999)
