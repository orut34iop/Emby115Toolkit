"""
services.metadata_copier 模块单元测试
"""

import os


class TestMetadataCopierInit:
    """测试 MetadataCopier 初始化"""

    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from services.metadata_copier import MetadataCopier

        copier = MetadataCopier(source_folders=[temp_dir], target_folder=temp_dir, allowed_extensions=('.nfo', '.jpg'))

        assert copier.source_folders == [temp_dir]
        assert copier.target_folder == temp_dir
        assert copier.metadata_extensions == ('.nfo', '.jpg')
        assert copier.thread_count == 1
        assert copier.only_tvshow_nfo == False
        assert copier.overwrite_existing == False

    def test_init_with_custom_values(self, temp_dir):
        """测试使用自定义值初始化"""
        from services.metadata_copier import MetadataCopier

        copier = MetadataCopier(
            source_folders=[temp_dir, '/another/path'],
            target_folder=temp_dir,
            allowed_extensions=('.nfo',),
            thread_count=4,
            only_tvshow_nfo=True,
            overwrite_existing=True,
        )

        assert copier.thread_count == 4
        assert copier.only_tvshow_nfo == True
        assert copier.overwrite_existing == True


class TestMetadataCopierGetSourceFiles:
    """测试 get_source_files 方法"""

    def test_get_nfo_files(self, temp_dir, create_test_file_structure):
        """测试获取 nfo 文件"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.nfo': 'nfo2',
            'movies/video.mp4': 'video',
        }
        create_test_file_structure(structure)

        copier = MetadataCopier(source_folders=[temp_dir], target_folder=temp_dir, allowed_extensions=('.nfo',))

        files = list(copier.get_source_files())

        assert len(files) == 2
        names = [os.path.basename(f[0]) for f in files]
        assert 'movie1.nfo' in names
        assert 'movie2.nfo' in names

    def test_get_jpg_files(self, temp_dir, create_test_file_structure):
        """测试获取 jpg 文件"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'movies/poster1.jpg': 'jpg1',
            'movies/poster2.png': 'png1',
        }
        create_test_file_structure(structure)

        copier = MetadataCopier(source_folders=[temp_dir], target_folder=temp_dir, allowed_extensions=('.jpg', '.png'))

        files = list(copier.get_source_files())

        assert len(files) == 2

    def test_only_tvshow_nfo_true(self, temp_dir, create_test_file_structure):
        """测试只获取 tvshow.nfo"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'tvshow/tvshow.nfo': 'show nfo',
            'tvshow/Season 1/episode.nfo': 'ep nfo',
            'tvshow/Season 1/episode.mp4': 'video',
        }
        create_test_file_structure(structure)

        copier = MetadataCopier(
            source_folders=[temp_dir], target_folder=temp_dir, allowed_extensions=('.nfo',), only_tvshow_nfo=True
        )

        files = list(copier.get_source_files())

        # 只有 tvshow.nfo 应该被找到
        assert len(files) == 1
        assert 'tvshow.nfo' in files[0][0]

    def test_skip_nonexistent_source(self, temp_dir):
        """测试跳过不存在的源文件夹"""
        from services.metadata_copier import MetadataCopier

        copier = MetadataCopier(
            source_folders=['/nonexistent/path'], target_folder=temp_dir, allowed_extensions=('.nfo',)
        )

        files = list(copier.get_source_files())

        assert len(files) == 0


class TestMetadataCopierCopy:
    """测试 copy_metadata 方法"""

    def test_copy_new_file(self, temp_dir, create_test_file_structure):
        """测试复制新文件"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'source/movie.nfo': 'nfo content',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copier = MetadataCopier(
            source_folders=[os.path.join(temp_dir, 'source')], target_folder=target_folder, allowed_extensions=('.nfo',)
        )

        files = list(copier.get_source_files())
        copier.copy_metadata(files[0][0], os.path.join(target_folder, 'movie.nfo'), 'TestThread')

        # 验证文件被复制
        assert os.path.exists(os.path.join(target_folder, 'movie.nfo'))
        with open(os.path.join(target_folder, 'movie.nfo'), 'r') as f:
            assert f.read() == 'nfo content'

    def test_skip_existing_file(self, temp_dir, create_test_file_structure):
        """测试跳过已存在的文件"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'source/movie.nfo': 'new content',
            'target/movie.nfo': 'existing content',
        }
        create_test_file_structure(structure)

        copier = MetadataCopier(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',),
        )

        copier.copy_metadata(
            os.path.join(temp_dir, 'source', 'movie.nfo'), os.path.join(temp_dir, 'target', 'movie.nfo'), 'TestThread'
        )

        # 验证现有文件未被覆盖
        with open(os.path.join(temp_dir, 'target', 'movie.nfo'), 'r') as f:
            assert f.read() == 'existing content'

    def test_overwrite_existing_file(self, temp_dir, create_test_file_structure):
        """测试覆盖已存在的文件"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'source/movie.nfo': 'new content',
            'target/movie.nfo': 'existing content',
        }
        create_test_file_structure(structure)

        copier = MetadataCopier(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=os.path.join(temp_dir, 'target'),
            allowed_extensions=('.nfo',),
            overwrite_existing=True,
        )

        copier.copy_metadata(
            os.path.join(temp_dir, 'source', 'movie.nfo'), os.path.join(temp_dir, 'target', 'movie.nfo'), 'TestThread'
        )

        with open(os.path.join(temp_dir, 'target', 'movie.nfo'), 'r') as f:
            assert f.read() == 'new content'
        assert copier.overwritten_metadatas == 1
        assert copier.existing_links == 0


class TestMetadataCopierRun:
    """测试 run 方法"""

    def test_run_complete_workflow(self, temp_dir, create_test_file_structure):
        """测试完整工作流程"""
        import time

        from services.metadata_copier import MetadataCopier

        structure = {
            'source/Movie1.nfo': 'nfo1',
            'source/Movie1.jpg': 'jpg1',
            'source/Movie2.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copier = MetadataCopier(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=target_folder,
            allowed_extensions=('.nfo', '.jpg'),
            thread_count=1,
        )

        messages = []

        def callback(msg):
            messages.append(msg)

        copier.run(callback)

        # 等待后台线程完成
        time.sleep(0.5)

        # 验证回调被调用
        assert len(messages) > 0

        # 验证文件被复制（与软链接创建保持一致，不额外包含源文件夹名）
        assert os.path.exists(os.path.join(target_folder, 'Movie1.nfo'))
        assert os.path.exists(os.path.join(target_folder, 'Movie1.jpg'))
        assert os.path.exists(os.path.join(target_folder, 'Movie2.nfo'))

    def test_run_preserves_each_source_folder_name_for_multiple_sources(
        self, temp_dir, create_test_file_structure
    ):
        """多源元数据复制应与软链接使用相同的影片目录结构。"""
        from services.metadata_copier import MetadataCopier

        structure = {
            'movies/谜印女子 (2026)/movie.nfo': 'nfo1',
            'movies/蕾切尔·尼克尔谋杀案 (2026)/movie.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        source_folders = [
            os.path.join(temp_dir, 'movies', '谜印女子 (2026)'),
            os.path.join(temp_dir, 'movies', '蕾切尔·尼克尔谋杀案 (2026)'),
        ]
        target_folder = os.path.join(temp_dir, 'target')
        copier = MetadataCopier(
            source_folders=source_folders,
            target_folder=target_folder,
            allowed_extensions=('.nfo',),
            thread_count=1,
        )

        thread = copier.run()
        thread.join()

        assert os.path.exists(os.path.join(target_folder, '谜印女子 (2026)', 'movie.nfo'))
        assert os.path.exists(os.path.join(target_folder, '蕾切尔·尼克尔谋杀案 (2026)', 'movie.nfo'))
        assert not os.path.exists(os.path.join(target_folder, 'movie.nfo'))

    def test_run_counters(self, temp_dir, create_test_file_structure):
        """测试计数器"""
        import time

        from services.metadata_copier import MetadataCopier

        structure = {
            'source/file1.nfo': 'nfo1',
            'source/file2.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        copier = MetadataCopier(
            source_folders=[os.path.join(temp_dir, 'source')],
            target_folder=target_folder,
            allowed_extensions=('.nfo',),
            thread_count=1,
        )

        copier.run(lambda msg: None)

        # 等待后台线程完成
        time.sleep(0.5)

        # 验证计数器
        assert copier.copied_metadatas == 2
        assert copier.existing_links == 0
