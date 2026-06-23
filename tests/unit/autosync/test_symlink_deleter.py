"""
autosync.SymlinkDeleter 模块单元测试
"""
import pytest
import os


class TestSymlinkDeleterInit:
    """测试 SymlinkDeleter 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        deleter = SymlinkDeleter(target_folder=temp_dir)

        assert deleter.target_folder == temp_dir
        assert deleter.symlink_name == "软链接"
        assert deleter.logger is not None

    def test_init_with_custom_logger(self, temp_dir):
        """测试使用自定义 logger 初始化"""
        from autosync.SymlinkDeleter import SymlinkDeleter
        import logging

        custom_logger = logging.getLogger("custom")
        deleter = SymlinkDeleter(target_folder=temp_dir, logger=custom_logger)

        assert deleter.logger == custom_logger


class TestSymlinkDeleterRun:
    """测试 run 方法"""

    def test_delete_single_symlink(self, temp_dir, create_test_file_structure):
        """测试删除单个符号链接"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        # 创建真实文件和符号链接
        structure = {
            'real_file.mp4': 'video content',
        }
        create_test_file_structure(structure)

        real_file = os.path.join(temp_dir, 'real_file.mp4')
        link_file = os.path.join(temp_dir, 'link_file.mp4')
        os.symlink(real_file, link_file)

        assert os.path.islink(link_file)

        deleter = SymlinkDeleter(target_folder=temp_dir)
        total_time, message = deleter.run()

        # 验证符号链接被删除
        assert not os.path.exists(link_file)
        # 验证真实文件未被删除
        assert os.path.exists(real_file)

    def test_delete_multiple_symlinks(self, temp_dir, create_test_file_structure):
        """测试删除多个符号链接"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        structure = {
            'real1.mp4': 'video1',
            'real2.mkv': 'video2',
        }
        create_test_file_structure(structure)

        # 创建多个符号链接
        for i in range(1, 4):
            link = os.path.join(temp_dir, f'link{i}.mp4')
            os.symlink(os.path.join(temp_dir, 'real1.mp4'), link)

        deleter = SymlinkDeleter(target_folder=temp_dir)
        total_time, message = deleter.run()

        # 验证所有符号链接被删除
        for i in range(1, 4):
            assert not os.path.exists(os.path.join(temp_dir, f'link{i}.mp4'))

    def test_skip_regular_files(self, temp_dir, create_test_file_structure):
        """测试跳过普通文件"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        structure = {
            'movie.mp4': 'video',
            'metadata.nfo': 'nfo',
        }
        create_test_file_structure(structure)

        deleter = SymlinkDeleter(target_folder=temp_dir)
        total_time, message = deleter.run()

        # 验证普通文件未被删除
        assert os.path.exists(os.path.join(temp_dir, 'movie.mp4'))
        assert os.path.exists(os.path.join(temp_dir, 'metadata.nfo'))

    def test_delete_symlinks_in_subdirectories(self, temp_dir, create_test_file_structure):
        """测试删除子目录中的符号链接"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        structure = {
            'source/movie.mp4': 'video',
        }
        create_test_file_structure(structure)

        # 在子目录中创建符号链接
        subdir = os.path.join(temp_dir, 'season1')
        os.makedirs(subdir, exist_ok=True)
        link = os.path.join(subdir, 'episode.mp4')
        os.symlink(os.path.join(temp_dir, 'source', 'movie.mp4'), link)

        deleter = SymlinkDeleter(target_folder=temp_dir)
        total_time, message = deleter.run()

        # 验证子目录中的符号链接被删除
        assert not os.path.exists(link)

    def test_return_message_format(self, temp_dir):
        """测试返回消息格式"""
        from autosync.SymlinkDeleter import SymlinkDeleter

        deleter = SymlinkDeleter(target_folder=temp_dir)
        total_time, message = deleter.run()

        assert isinstance(total_time, float)
        assert total_time >= 0
        assert isinstance(message, str)
        assert '软链接' in message
