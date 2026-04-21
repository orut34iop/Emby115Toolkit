"""
autosync.SymlinkChecker 模块单元测试
"""
import pytest
import os


class TestSymlinkCheckerInit:
    """测试 SymlinkChecker 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.SymlinkChecker import SymlinkChecker

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        assert checker.cloud_path == temp_dir
        assert checker.source_folder == temp_dir
        assert checker.target_folder == temp_dir
        assert checker.symlink_mode == 'symlink'
        assert checker.num_threads == 4
        assert checker.total_num == 0
        assert checker.broken_num == 0

    def test_init_strm_mode(self, temp_dir):
        """测试 strm 模式初始化"""
        from autosync.SymlinkChecker import SymlinkChecker

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='strm'
        )

        assert checker.symlink_mode == 'strm'
        assert checker.symlink_name == 'strm文件'


class TestSymlinkCheckerGetSymlinkFiles:
    """测试 get_symlink_files 方法"""

    def test_get_symlink_files(self, temp_dir, create_test_file_structure):
        """测试获取符号链接文件"""
        from autosync.SymlinkChecker import SymlinkChecker

        structure = {
            'real.mp4': 'video',
        }
        create_test_file_structure(structure)

        # 创建符号链接
        os.symlink(
            os.path.join(temp_dir, 'real.mp4'),
            os.path.join(temp_dir, 'link.mp4')
        )

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        files = list(checker.get_symlink_files())

        assert len(files) == 1
        assert files[0].endswith('link.mp4')

    def test_skip_regular_files(self, temp_dir, create_test_file_structure):
        """测试跳过普通文件"""
        from autosync.SymlinkChecker import SymlinkChecker

        structure = {
            'movie.mp4': 'video',
        }
        create_test_file_structure(structure)

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        files = list(checker.get_symlink_files())

        assert len(files) == 0

    def test_symlink_mode_removes_strm_files(self, temp_dir, create_test_file_structure):
        """测试 symlink 模式下删除 strm 文件"""
        from autosync.SymlinkChecker import SymlinkChecker

        structure = {
            'movie.strm': 'strm content',
        }
        create_test_file_structure(structure)

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        files = list(checker.get_symlink_files())

        # strm 文件应该被删除，不会被 yield
        assert len(files) == 0
        assert not os.path.exists(os.path.join(temp_dir, 'movie.strm'))


class TestSymlinkCheckerCheckAndRemove:
    """测试 check_and_remove_dead_symlink 方法"""

    def test_remove_broken_symlink(self, temp_dir, create_test_file_structure):
        """测试删除无效的符号链接"""
        from autosync.SymlinkChecker import SymlinkChecker

        # 创建符号链接指向不存在的文件
        link_path = os.path.join(temp_dir, 'broken_link.mp4')
        os.symlink('/nonexistent/path/file.mp4', link_path)

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        checker.check_and_remove_dead_symlink(link_path)

        assert not os.path.exists(link_path)
        assert checker.total_num == 1
        assert checker.broken_num == 1

    def test_keep_valid_symlink(self, temp_dir, create_test_file_structure):
        """测试保留有效的符号链接"""
        from autosync.SymlinkChecker import SymlinkChecker

        structure = {
            'real.mp4': 'video',
        }
        create_test_file_structure(structure)

        link_path = os.path.join(temp_dir, 'valid_link.mp4')
        os.symlink(os.path.join(temp_dir, 'real.mp4'), link_path)

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        checker.check_and_remove_dead_symlink(link_path)

        assert os.path.exists(link_path)
        assert checker.total_num == 1
        assert checker.broken_num == 0

    def test_skip_when_cloud_path_missing(self, temp_dir, create_test_file_structure):
        """测试 cloud_path 不存在时跳过删除"""
        from autosync.SymlinkChecker import SymlinkChecker

        link_path = os.path.join(temp_dir, 'broken_link.mp4')
        os.symlink('/nonexistent/path/file.mp4', link_path)

        checker = SymlinkChecker(
            cloud_path='/nonexistent/cloud/path',
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink'
        )

        checker.check_and_remove_dead_symlink(link_path)

        # cloud_path 不存在时不应删除（使用 lexists 检查 symlink 本身是否存在）
        assert os.path.lexists(link_path)


class TestSymlinkCheckerRun:
    """测试 run 方法"""

    def test_run_with_broken_symlinks(self, temp_dir, create_test_file_structure):
        """测试运行并清理无效链接"""
        from autosync.SymlinkChecker import SymlinkChecker

        # 创建无效符号链接
        for i in range(3):
            link_path = os.path.join(temp_dir, f'broken_{i}.mp4')
            os.symlink('/nonexistent/file.mp4', link_path)

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink',
            num_threads=1
        )

        total_time, message = checker.run()

        # 验证所有无效链接被删除
        for i in range(3):
            assert not os.path.exists(os.path.join(temp_dir, f'broken_{i}.mp4'))

        assert checker.total_num == 3
        assert checker.broken_num == 3
        assert isinstance(total_time, float)
        assert isinstance(message, str)

    def test_run_with_no_symlinks(self, temp_dir):
        """测试没有符号链接的情况"""
        from autosync.SymlinkChecker import SymlinkChecker

        checker = SymlinkChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            symlink_mode='symlink',
            num_threads=1
        )

        total_time, message = checker.run()

        assert checker.total_num == 0
        assert checker.broken_num == 0
