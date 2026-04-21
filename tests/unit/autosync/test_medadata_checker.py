"""
autosync.MedadaChecker 模块单元测试
"""
import pytest
import os


class TestMedadadaCheckerInit:
    """测试 MedadadaChecker 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.MedadataChecker import MetadadaChecker

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            allowed_extensions=('.nfo', '.jpg')
        )

        assert checker.cloud_path == temp_dir
        assert checker.source_folder == temp_dir
        assert checker.target_folder == temp_dir
        assert checker.allowed_extensions == ('.nfo', '.jpg')
        assert checker.num_threads == 4
        assert checker.total_num == 0
        assert checker.broken_num == 0


class TestMedadadaCheckerGetMetadataFiles:
    """测试 get_metadata_files 方法"""

    def test_get_nfo_files(self, temp_dir, create_test_file_structure):
        """测试获取 nfo 文件"""
        from autosync.MedadataChecker import MetadadaChecker

        structure = {
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.nfo': 'nfo2',
            'movies/video.mp4': 'video',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            allowed_extensions=('.nfo',)
        )

        files = list(checker.get_metadata_files())

        assert len(files) == 2
        assert all(f.endswith('.nfo') for f in files)

    def test_get_mixed_extensions(self, temp_dir, create_test_file_structure):
        """测试获取多种扩展名文件"""
        from autosync.MedadataChecker import MetadadaChecker

        structure = {
            'movies/movie.nfo': 'nfo',
            'movies/poster.jpg': 'jpg',
            'movies/poster.png': 'png',
            'movies/video.mp4': 'video',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            allowed_extensions=('.nfo', '.jpg')
        )

        files = list(checker.get_metadata_files())

        assert len(files) == 2


class TestMedadadaCheckerCheckAndRemove:
    """测试 check_and_remove_dead_metadata 方法"""

    def test_remove_dead_metadata(self, temp_dir, create_test_file_structure):
        """测试删除无效元数据"""
        from autosync.MedadataChecker import MetadadaChecker

        # 在目标目录创建元数据文件，但源目录不存在对应文件
        structure = {
            'target/movie.nfo': 'nfo content',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=os.path.join(temp_dir, 'source'),
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',)
        )

        metadata_path = os.path.join(temp_dir, 'target', 'movie.nfo')
        checker.check_and_remove_dead_metadata(metadata_path)

        assert not os.path.exists(metadata_path)
        assert checker.total_num == 1
        assert checker.broken_num == 1

    def test_keep_valid_metadata(self, temp_dir, create_test_file_structure):
        """测试保留有效元数据"""
        from autosync.MedadataChecker import MetadadaChecker

        structure = {
            'source/movie.nfo': 'source nfo',
            'target/movie.nfo': 'target nfo',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=os.path.join(temp_dir, 'source'),
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',)
        )

        metadata_path = os.path.join(temp_dir, 'target', 'movie.nfo')
        checker.check_and_remove_dead_metadata(metadata_path)

        assert os.path.exists(metadata_path)
        assert checker.total_num == 1
        assert checker.broken_num == 0

    def test_skip_when_cloud_path_missing(self, temp_dir, create_test_file_structure):
        """测试 cloud_path 不存在时跳过删除"""
        from autosync.MedadataChecker import MetadadaChecker

        structure = {
            'target/movie.nfo': 'nfo content',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path='/nonexistent/cloud',
            source_folder=os.path.join(temp_dir, 'source'),
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',)
        )

        metadata_path = os.path.join(temp_dir, 'target', 'movie.nfo')
        checker.check_and_remove_dead_metadata(metadata_path)

        assert os.path.exists(metadata_path)


class TestMedadadaCheckerRun:
    """测试 run 方法"""

    def test_run_removes_dead_metadata(self, temp_dir, create_test_file_structure):
        """测试运行并清理无效元数据"""
        from autosync.MedadataChecker import MetadadaChecker

        structure = {
            'target/movie1.nfo': 'nfo1',
            'target/movie2.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=os.path.join(temp_dir, 'source'),
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',),
            num_threads=1
        )

        total_time, message = checker.run()

        # 所有元数据都应该被删除（因为源文件不存在）
        assert not os.path.exists(os.path.join(temp_dir, 'target', 'movie1.nfo'))
        assert not os.path.exists(os.path.join(temp_dir, 'target', 'movie2.nfo'))
        assert checker.total_num == 2
        assert checker.broken_num == 2
        assert isinstance(total_time, float)
        assert isinstance(message, str)

    def test_run_with_no_metadata(self, temp_dir):
        """测试没有元数据的情况"""
        from autosync.MedadataChecker import MetadadaChecker

        checker = MetadadaChecker(
            cloud_path=temp_dir,
            source_folder=temp_dir,
            target_folder=temp_dir,
            allowed_extensions=('.nfo',),
            num_threads=1
        )

        total_time, message = checker.run()

        assert checker.total_num == 0
        assert checker.broken_num == 0
