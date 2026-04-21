"""
autosync.SymlinkDirChecker 模块单元测试
"""
import pytest
import os


class TestSymlinkDirCheckerInit:
    """测试 SymlinkDirChecker 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=temp_dir,
            target_root=temp_dir
        )

        assert checker.cloud_path == temp_dir
        assert checker.source_root == temp_dir
        assert checker.target_root == temp_dir
        assert checker.num_threads == 8
        assert checker.timeout_seconds == 300
        assert checker.error_dirs_num == 0
        assert checker.total_num == 0

    def test_init_with_custom_values(self, temp_dir):
        """测试使用自定义值初始化"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=temp_dir,
            target_root=temp_dir,
            num_threads=4,
            timeout_seconds=60
        )

        assert checker.num_threads == 4
        assert checker.timeout_seconds == 60


class TestSymlinkDirCheckerGetDirs:
    """测试 get_dirs 方法"""

    def test_get_dirs(self, temp_dir, create_test_file_structure):
        """测试获取目录列表"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        structure = {
            'folder1/subfolder': None,
            'folder2': None,
        }
        create_test_file_structure(structure)

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=temp_dir,
            target_root=temp_dir
        )

        dirs = list(checker.get_dirs())

        assert len(dirs) == 3  # folder1, folder1/subfolder, folder2

    def test_get_dirs_empty(self, temp_dir):
        """测试空目录"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=temp_dir,
            target_root=temp_dir
        )

        dirs = list(checker.get_dirs())

        assert len(dirs) == 0


class TestSymlinkDirCheckerRemoveErrorDir:
    """测试 remove_error_dir 方法"""

    def test_remove_error_dir_when_target_missing(self, temp_dir, create_test_file_structure):
        """测试目标目录不存在时删除源目录"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        structure = {
            'source/movie1': None,
            'source/movie2': None,
        }
        create_test_file_structure(structure)

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=os.path.join(temp_dir, 'source'),
            target_root=os.path.join(temp_dir, 'target')
        )

        dir_path = os.path.join(temp_dir, 'source', 'movie1')
        checker.file_queue.put(dir_path)
        checker.file_queue.put(None)
        checker.remove_error_dir('TestThread')

        assert not os.path.exists(dir_path)
        assert checker.error_dirs_num == 1
        assert checker.total_num == 1

    def test_keep_dir_when_target_exists(self, temp_dir, create_test_file_structure):
        """测试目标目录存在时保留源目录"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        structure = {
            'source/movie1': None,
            'target/movie1': None,
        }
        create_test_file_structure(structure)

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=os.path.join(temp_dir, 'source'),
            target_root=os.path.join(temp_dir, 'target')
        )

        dir_path = os.path.join(temp_dir, 'source', 'movie1')
        checker.file_queue.put(dir_path)
        checker.file_queue.put(None)
        checker.remove_error_dir('TestThread')

        assert os.path.exists(dir_path)
        assert checker.error_dirs_num == 0
        assert checker.total_num == 1

    def test_skip_when_cloud_path_missing(self, temp_dir, create_test_file_structure):
        """测试 cloud_path 不存在时跳过删除"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        structure = {
            'source/movie1': None,
        }
        create_test_file_structure(structure)

        checker = SymlinkDirChecker(
            cloud_path='/nonexistent/cloud',
            source_root=os.path.join(temp_dir, 'source'),
            target_root=os.path.join(temp_dir, 'target')
        )

        dir_path = os.path.join(temp_dir, 'source', 'movie1')
        checker.file_queue.put(dir_path)
        checker.file_queue.put(None)
        checker.remove_error_dir('TestThread')

        assert os.path.exists(dir_path)


class TestSymlinkDirCheckerRun:
    """测试 run 方法"""

    def test_run_removes_error_dirs(self, temp_dir, create_test_file_structure):
        """测试运行并清理失效目录"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        structure = {
            'source/movie1': None,
            'source/movie2': None,
        }
        create_test_file_structure(structure)

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=os.path.join(temp_dir, 'source'),
            target_root=os.path.join(temp_dir, 'target'),
            num_threads=1
        )

        total_time, message = checker.run()

        # 所有源目录都应该被删除（因为目标目录不存在）
        assert not os.path.exists(os.path.join(temp_dir, 'source', 'movie1'))
        assert not os.path.exists(os.path.join(temp_dir, 'source', 'movie2'))
        assert checker.error_dirs_num == 2
        assert isinstance(total_time, float)
        assert isinstance(message, str)

    def test_run_with_no_dirs(self, temp_dir):
        """测试没有子目录的情况"""
        from autosync.SymlinkDirChecker import SymlinkDirChecker

        checker = SymlinkDirChecker(
            cloud_path=temp_dir,
            source_root=temp_dir,
            target_root=temp_dir,
            num_threads=1
        )

        total_time, message = checker.run()

        assert checker.total_num == 0
        assert checker.error_dirs_num == 0
