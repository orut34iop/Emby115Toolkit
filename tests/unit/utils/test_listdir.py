"""
utils.listdir 模块单元测试
"""
import pytest
import os


class TestListFiles:
    """测试 list_files 函数"""
    
    def test_list_files_basic(self, temp_dir, create_test_file_structure):
        """测试基本的文件列表功能"""
        from utils.listdir import list_files
        
        structure = {
            'folder1/movie1.mp4': 'content1',
            'folder1/movie2.mkv': 'content2',
            'folder1/subtitle.srt': 'subtitle content',
            'folder2/movie3.avi': 'content3',
        }
        create_test_file_structure(structure)
        
        file_count, output_path = list_files(temp_dir)
        
        assert file_count == 4
        assert output_path != ""
        assert os.path.exists(output_path)
    
    def test_list_files_empty_folder(self, temp_dir):
        """测试空文件夹"""
        from utils.listdir import list_files
        
        file_count, output_path = list_files(temp_dir)
        
        assert file_count == 0
        assert output_path == ""
    
    def test_list_files_nested_structure(self, temp_dir, create_test_file_structure):
        """测试嵌套目录结构"""
        from utils.listdir import list_files
        
        structure = {
            'level1/level2/level3/deep_file.mp4': 'deep content',
            'level1/shallow_file.mkv': 'shallow content',
        }
        create_test_file_structure(structure)
        
        file_count, output_path = list_files(temp_dir)
        
        assert file_count == 2
        assert output_path != ""
        
        # 验证输出文件包含所有文件路径
        with open(output_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        paths = [line.strip() for line in lines]
        assert any('level3' in p for p in paths)
        assert any('shallow' in p for p in paths)
    
    def test_list_files_nonexistent_folder(self):
        """测试不存在的文件夹"""
        from utils.listdir import list_files
        
        file_count, output_path = list_files('/nonexistent/path/that/does/not/exist')
        
        assert file_count == 0
        assert output_path == ""
    
    def test_list_files_output_file_created(self, temp_dir, create_test_file_structure):
        """测试输出文件被正确创建"""
        from utils.listdir import list_files
        
        structure = {
            'test.txt': 'content',
        }
        create_test_file_structure(structure)
        
        file_count, output_path = list_files(temp_dir)
        
        assert os.path.exists(output_path)
        assert output_path.endswith('.txt')
        
        # 验证文件内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'test.txt' in content
    
    def test_list_files_with_logger(self, temp_dir, create_test_file_structure):
        """测试带日志记录器的文件列表"""
        from utils.listdir import list_files
        import logging
        
        structure = {
            'movie.mp4': 'video content',
        }
        create_test_file_structure(structure)
        
        logger = logging.getLogger('test_logger')
        file_count, output_path = list_files(temp_dir, logger=logger)
        
        assert file_count == 1
        assert output_path != ""


class TestGetFileCount:
    """测试 get_file_count 函数"""
    
    def test_get_file_count_basic(self, temp_dir, create_test_file_structure):
        """测试基本的文件计数功能"""
        from utils.listdir import get_file_count
        
        structure = {
            'folder1/movie1.mp4': 'content1',
            'folder1/movie2.mkv': 'content2',
            'folder2/movie3.avi': 'content3',
        }
        create_test_file_structure(structure)
        
        result = get_file_count(temp_dir)
        
        assert result == 3
    
    def test_get_file_count_empty(self, temp_dir):
        """测试空目录"""
        from utils.listdir import get_file_count
        
        result = get_file_count(temp_dir)
        
        assert result == 0
    
    def test_get_file_count_nested(self, temp_dir, create_test_file_structure):
        """测试嵌套目录"""
        from utils.listdir import get_file_count
        
        structure = {
            'a/b/c/d/deep.mp4': 'deep',
            'a/b/shallow.mkv': 'shallow',
            'root.txt': 'root',
        }
        create_test_file_structure(structure)
        
        result = get_file_count(temp_dir)
        
        assert result == 3
    
    def test_get_file_count_nonexistent(self):
        """测试不存在的目录"""
        from utils.listdir import get_file_count
        
        result = get_file_count('/nonexistent/path')
        
        assert result == 0
    
    def test_get_file_count_directories_only(self, temp_dir, create_test_file_structure):
        """测试只有目录没有文件"""
        from utils.listdir import get_file_count
        
        structure = {
            'folder1/subfolder': None,
            'folder2': None,
        }
        create_test_file_structure(structure)
        
        result = get_file_count(temp_dir)
        
        assert result == 0


class TestGenerateOutputFilename:
    """测试 generate_output_filename 函数"""
    
    def test_generate_output_filename(self):
        """测试生成输出文件名"""
        from utils.listdir import generate_output_filename
        
        result = generate_output_filename('/test/folder')
        
        assert 'folder' in result
        assert 'files_' in result
        assert result.endswith('.txt')
    
    def test_generate_output_filename_with_trailing_slash(self):
        """测试带尾部斜杠的路径"""
        from utils.listdir import generate_output_filename
        
        result = generate_output_filename('/test/folder/')
        
        assert 'folder' in result
        assert result.endswith('.txt')
    
    def test_generate_output_filename_unique(self):
        """测试生成的文件名包含时间戳"""
        from utils.listdir import generate_output_filename
        import time
        
        result = generate_output_filename('/test/folder')
        
        # 应该包含时间戳格式 YYYYMMDD_HHMMSS
        assert len(result) > len('folder_files_.txt')
        # 验证包含数字（时间戳）
        assert any(c.isdigit() for c in result)