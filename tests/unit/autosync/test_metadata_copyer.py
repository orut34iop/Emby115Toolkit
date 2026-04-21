"""
autosync.MetadataCopyer 模块单元测试
"""
import pytest
import os


class TestMetadataCopyerInit:
    """测试 MetadataCopyer 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.MetadataCopyer import MetadataCopyer

        copyer = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=('.nfo', '.jpg')
        )

        assert copyer.source_folders == [temp_dir]
        assert copyer.target_folder == temp_dir
        assert copyer.metadata_extensions == ('.nfo', '.jpg')
        assert copyer.num_threads == 1
        assert copyer.only_tvshow_nfo == False

    def test_init_with_custom_values(self, temp_dir):
        """测试使用自定义值初始化"""
        from autosync.MetadataCopyer import MetadataCopyer

        copyer = MetadataCopyer(
            source_folders=[temp_dir, '/another/path'],
            target_folder=temp_dir,
            allowed_extensions=('.nfo',),
            num_threads=4,
            only_tvshow_nfo=True
        )

        assert copyer.num_threads == 4
        assert copyer.only_tvshow_nfo == True


class TestMetadataCopyerGetSourceFiles:
    """测试 get_source_files 方法"""

    def test_get_nfo_files(self, temp_dir, create_test_file_structure):
        """测试获取 nfo 文件"""
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.nfo': 'nfo2',
            'movies/video.mp4': 'video',
        }
        create_test_file_structure(structure)

        copyer = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=('.nfo',)
        )

        files = list(copyer.get_source_files())

        assert len(files) == 2
        names = [os.path.basename(f[0]) for f in files]
        assert 'movie1.nfo' in names
        assert 'movie2.nfo' in names

    def test_get_jpg_files(self, temp_dir, create_test_file_structure):
        """测试获取 jpg 文件"""
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'movies/poster1.jpg': 'jpg1',
            'movies/poster2.png': 'png1',
        }
        create_test_file_structure(structure)

        copyer = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=('.jpg', '.png')
        )

        files = list(copyer.get_source_files())

        assert len(files) == 2

    def test_only_tvshow_nfo_true(self, temp_dir, create_test_file_structure):
        """测试只获取 tvshow.nfo"""
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'tvshow/tvshow.nfo': 'show nfo',
            'tvshow/Season 1/episode.nfo': 'ep nfo',
            'tvshow/Season 1/episode.mp4': 'video',
        }
        create_test_file_structure(structure)

        copyer = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=('.nfo',),
            only_tvshow_nfo=True
        )

        files = list(copyer.get_source_files())

        # 只有 tvshow.nfo 应该被找到
        assert len(files) == 1
        assert 'tvshow.nfo' in files[0][0]

    def test_skip_nonexistent_source(self, temp_dir):
        """测试跳过不存在的源文件夹"""
        from autosync.MetadataCopyer import MetadataCopyer

        copyer = MetadataCopyer(
            source_folders=['/nonexistent/path'],
            target_folder=temp_dir,
            allowed_extensions=('.nfo',)
        )

        files = list(copyer.get_source_files())

        assert len(files) == 0


class TestMetadataCopyerCopy:
    """测试 copy_metadata 方法"""

    def test_copy_new_file(self, temp_dir, create_test_file_structure):
        """测试复制新文件"""
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'source/movie.nfo': 'nfo content',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copyer = MetadataCopyer(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=target_folder,
            allowed_extensions=('.nfo',)
        )

        files = list(copyer.get_source_files())
        copyer.copy_metadata(files[0][0], os.path.join(target_folder, 'movie.nfo'), 'TestThread')

        # 验证文件被复制
        assert os.path.exists(os.path.join(target_folder, 'movie.nfo'))
        with open(os.path.join(target_folder, 'movie.nfo'), 'r') as f:
            assert f.read() == 'nfo content'

    def test_skip_existing_file(self, temp_dir, create_test_file_structure):
        """测试跳过已存在的文件"""
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'source/movie.nfo': 'new content',
            'target/movie.nfo': 'existing content',
        }
        create_test_file_structure(structure)

        copyer = MetadataCopyer(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',)
        )

        copyer.copy_metadata(
            os.path.join(temp_dir, 'source', 'movie.nfo'),
            os.path.join(temp_dir, 'target', 'movie.nfo'),
            'TestThread'
        )

        # 验证现有文件未被覆盖
        with open(os.path.join(temp_dir, 'target', 'movie.nfo'), 'r') as f:
            assert f.read() == 'existing content'


class TestMetadataCopyerRun:
    """测试 run 方法"""

    def test_run_complete_workflow(self, temp_dir, create_test_file_structure):
        """测试完整工作流程"""
        import time
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'source/Movie1.nfo': 'nfo1',
            'source/Movie1.jpg': 'jpg1',
            'source/Movie2.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copyer = MetadataCopyer(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=target_folder,
            allowed_extensions=('.nfo', '.jpg'),
            num_threads=1
        )

        messages = []

        def callback(msg):
            messages.append(msg)

        copyer.run(callback)

        # 等待后台线程完成
        time.sleep(0.5)

        # 验证回调被调用
        assert len(messages) > 0

        # 验证文件被复制（保留了源文件夹的相对路径结构）
        assert os.path.exists(os.path.join(target_folder, 'source', 'Movie1.nfo'))
        assert os.path.exists(os.path.join(target_folder, 'source', 'Movie1.jpg'))
        assert os.path.exists(os.path.join(target_folder, 'source', 'Movie2.nfo'))

    def test_run_counters(self, temp_dir, create_test_file_structure):
        """测试计数器"""
        import time
        from autosync.MetadataCopyer import MetadataCopyer

        structure = {
            'source/file1.nfo': 'nfo1',
            'source/file2.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copyer = MetadataCopyer(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=target_folder,
            allowed_extensions=('.nfo',),
            num_threads=1
        )

        copyer.run(lambda msg: None)

        # 等待后台线程完成
        time.sleep(0.5)

        # 验证计数器
        assert copyer.copied_metadatas == 2
        assert copyer.existing_links == 0
