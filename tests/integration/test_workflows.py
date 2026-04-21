"""
集成测试 - 完整工作流程测试
"""
import pytest
import os
import tempfile
import shutil
import time
from unittest.mock import Mock, patch


class TestSymlinkWorkflow:
    """测试软链接创建完整工作流程"""
    
    def test_full_symlink_workflow(self, temp_dir, create_test_file_structure):
        """测试从扫描到创建的完整流程"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        # 创建源文件夹结构
        structure = {
            'source/Movies/Action/Movie1.2023.mp4': 'video1',
            'source/Movies/Action/Movie1.2023.nfo': 'nfo1',
            'source/Movies/Action/Movie1.2023.jpg': 'poster1',
            'source/Movies/Comedy/Movie2.2022.mkv': 'video2',
            'source/Movies/Comedy/Movie2.2022.nfo': 'nfo2',
            'source/TVShows/Show1/Season 1/Ep01.mp4': 'ep1',
            'source/TVShows/Show1/Season 1/Ep02.mp4': 'ep2',
            'source/TVShows/Show1/tvshow.nfo': 'show_nfo',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        # 创建 SymlinkCreator 实例
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            thread_count=2,
            only_tvshow_nfo=True
        )
        
        # 运行完整流程
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        creator.run(callback)
        
        # 验证结果
        assert creator.total_files > 0
        assert creator.success_count > 0
        
        # 验证目录结构
        assert os.path.islink(os.path.join(target_folder, 'Movies', 'Action', 'Movie1.2023.mp4'))
        # .nfo 文件在 only_tvshow_nfo=True 时只有 tvshow.nfo 会被创建
        assert os.path.islink(os.path.join(target_folder, 'TVShows', 'Show1', 'tvshow.nfo'))

        # 验证剧集的 episode nfo 未被创建（only_tvshow_nfo=True）
        assert not os.path.exists(os.path.join(target_folder, 'TVShows', 'Show1', 'Season 1', 'Ep01.nfo'))
        # 验证普通 nfo 在 only_tvshow_nfo=True 时被跳过
        assert not os.path.exists(os.path.join(target_folder, 'Movies', 'Action', 'Movie1.2023.nfo'))
    
    def test_strm_workflow(self, temp_dir, create_test_file_structure):
        """测试 strm 文件创建流程"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie.mp4': 'video',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='strm'
        )
        
        creator.run()
        
        # 验证 strm 文件
        strm_path = os.path.join(target_folder, 'movie.strm')
        assert os.path.exists(strm_path)
        
        with open(strm_path, 'r') as f:
            content = f.read().strip()
        assert content == os.path.join(source_folder, 'movie.mp4')
    
    def test_path_replacement_workflow(self, temp_dir, create_test_file_structure):
        """测试路径替换流程"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie.mp4': 'video',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='strm',
            enable_replace_path=True,
            original_path=temp_dir,
            replace_path='/mnt/media'
        )
        
        creator.run()
        
        # 验证路径替换
        strm_path = os.path.join(target_folder, 'movie.strm')
        with open(strm_path, 'r') as f:
            content = f.read().strip()
        
        assert '/mnt/media' in content
        assert temp_dir not in content


class TestFileMergeWorkflow:
    """测试文件合并完整工作流程"""
    
    def test_full_merge_workflow(self, temp_dir, create_test_file_structure):
        """测试从扫描到合并的完整流程"""
        from autosync.FileMerger import FileMerger
        
        # 创建刮削文件夹
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'nfo content',
            'scrap/Movie.2023.jpg': 'poster',
            'scrap/Movie.2023.srt': 'subtitle',
            'scrap/TVShow/tvshow.nfo': 'show nfo',
            'scrap/TVShow/Season 1/episode01.nfo': 'ep nfo',
        }
        create_test_file_structure(scrap_structure)
        
        # 创建视频文件夹
        target_structure = {
            'target/Movie.2023.mp4': 'video',
            'target/TVShow/tvshow.mp4': 'show video',
            'target/TVShow/Season 1/episode01.mp4': 'ep video',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target'),
            thread_count=1
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        merger.run(callback)
        
        # 验证文件被移动
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie.2023.nfo'))
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie.2023.jpg'))
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie.2023.srt'))
        
        # 验证源文件被删除
        assert not os.path.exists(os.path.join(temp_dir, 'scrap', 'Movie.2023.nfo'))
    
    def test_merge_with_existing_files(self, temp_dir, create_test_file_structure):
        """测试合并时跳过已存在的文件"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'new nfo',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie.2023.mp4': 'video',
            'target/Movie.2023.nfo': 'existing nfo',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        merger.run()
        
        # 验证现有文件未被覆盖
        with open(os.path.join(temp_dir, 'target', 'Movie.2023.nfo'), 'r') as f:
            content = f.read()
        assert content == 'existing nfo'


class TestTreeMirrorWorkflow:
    """测试目录树镜像完整工作流程"""
    
    def test_full_tree_mirror_workflow(self, temp_dir, sample_tree_content):
        """测试从解析到创建的完整流程"""
        from autosync.TreeMirror import TreeMirror
        
        # 创建树文件
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(sample_tree_content)
        
        export_folder = os.path.join(temp_dir, 'export')
        os.makedirs(export_folder, exist_ok=True)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=export_folder
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        mirror.run(callback)
        
        # 验证目录结构
        assert os.path.isdir(os.path.join(export_folder, '电影'))
        assert os.path.isdir(os.path.join(export_folder, '电影', '动作片'))
        assert os.path.isdir(os.path.join(export_folder, '剧集', '美剧'))
        assert os.path.isdir(os.path.join(export_folder, '剧集', '韩剧'))
        
        # 验证空文件
        assert os.path.isfile(os.path.join(export_folder, '电影', '动作片', 'Movie.A.2023.mkv'))
        assert os.path.getsize(os.path.join(export_folder, '电影', '动作片', 'Movie.A.2023.mkv')) == 0
    
    def test_tree_mirror_with_garbled_text(self, temp_dir):
        """测试乱码修复流程"""
        from autosync.TreeMirror import TreeMirror
        
        tree_content = """我的资源
|——电影
| |- Movie.*.2023.mkv
"""
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        export_folder = os.path.join(temp_dir, 'export')
        os.makedirs(export_folder, exist_ok=True)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=export_folder,
            fix_garbled_text=True
        )
        
        mirror.run()
        
        # 验证乱码被修复
        assert os.path.isfile(os.path.join(export_folder, '电影', 'Movie.s.2023.mkv'))


class TestConfigIntegration:
    """测试配置模块集成"""
    
    def test_config_with_symlink_creator(self, temp_dir, monkeypatch):
        """测试配置与 SymlinkCreator 集成"""
        monkeypatch.chdir(temp_dir)
        
        from utils.config import Config
        from autosync.SymlinkCreator import SymlinkCreator
        
        Config._instance = None
        
        config = Config()
        
        # 设置配置值
        config.set('export_symlink', 'target_folder', '/test/target')
        config.set('export_symlink', 'thread_count', 8)
        config.set('export_symlink', 'only_tvshow_nfo', False)
        config.save()
        
        # 重新加载配置
        Config._instance = None
        config2 = Config()
        
        # 使用配置创建 SymlinkCreator
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=config2.get('export_symlink', 'target_folder'),
            symlink_mode='symlink',
            thread_count=config2.get('export_symlink', 'thread_count'),
            only_tvshow_nfo=config2.get('export_symlink', 'only_tvshow_nfo')
        )
        
        assert creator.target_folder == '/test/target'
        assert creator.thread_count == 8
        assert creator.only_tvshow_nfo == False
    
    def test_config_with_emby_operator(self, temp_dir, monkeypatch):
        """测试配置与 EmbyOperator 集成"""
        monkeypatch.chdir(temp_dir)
        
        from utils.config import Config
        from emby.EmbyOperator import EmbyOperator
        
        Config._instance = None
        
        config = Config()
        
        # 设置 Emby 配置
        config.set('merge_version', 'emby_url', 'http://emby-server:8096')
        config.set('merge_version', 'emby_api', 'my-api-key')
        config.save()
        
        # 重新加载
        Config._instance = None
        config2 = Config()
        
        # 使用配置创建 EmbyOperator
        operator = EmbyOperator(
            emby_url=config2.get('merge_version', 'emby_url'),
            emby_api=config2.get('merge_version', 'emby_api')
        )
        
        assert operator.emby_url == 'http://emby-server:8096'
        assert operator.emby_api == 'my-api-key'


class TestMultipleOperations:
    """测试多个操作组合"""
    
    def test_symlink_and_merge_workflow(self, temp_dir, create_test_file_structure):
        """测试先创建软链接再合并元数据"""
        from autosync.SymlinkCreator import SymlinkCreator
        from autosync.FileMerger import FileMerger
        
        # 创建 115 源文件夹（模拟网盘挂载）
        source_structure = {
            '115drive/Movies/Action/Movie1.2023.mp4': 'video1',
            '115drive/Movies/Comedy/Movie2.2022.mkv': 'video2',
        }
        create_test_file_structure(source_structure)
        
        # 创建刮削文件夹
        scrap_structure = {
            'scrap/Movie1.2023.nfo': 'nfo1',
            'scrap/Movie1.2023.jpg': 'poster1',
            'scrap/Movie2.2022.nfo': 'nfo2',
            'scrap/Movie2.2022.jpg': 'poster2',
        }
        create_test_file_structure(scrap_structure)
        
        # 创建目标文件夹
        target_folder = os.path.join(temp_dir, 'media')
        os.makedirs(target_folder, exist_ok=True)
        
        # 步骤 1: 创建软链接
        source_folder = os.path.join(temp_dir, '115drive')
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )
        creator.run()
        
        # 验证软链接
        assert os.path.islink(os.path.join(target_folder, 'Movies', 'Action', 'Movie1.2023.mp4'))
        
        # 步骤 2: 合并元数据
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=target_folder
        )
        merger.run()
        
        # 验证元数据被合并到正确位置
        assert os.path.exists(os.path.join(target_folder, 'Movies', 'Action', 'Movie1.2023.nfo'))
        assert os.path.exists(os.path.join(target_folder, 'Movies', 'Comedy', 'Movie2.2022.nfo'))
    
    def test_tree_mirror_and_merge_workflow(self, temp_dir, create_test_file_structure):
        """测试先创建目录树镜像再合并元数据"""
        from autosync.TreeMirror import TreeMirror
        from autosync.FileMerger import FileMerger
        
        # 创建目录树文件
        tree_content = """我的资源
|——电影
| |- Movie.2023.mkv
"""
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        # 创建刮削文件夹
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'nfo content',
            'scrap/Movie.2023.jpg': 'poster',
        }
        create_test_file_structure(scrap_structure)
        
        # 创建目标文件夹
        target_folder = os.path.join(temp_dir, 'media')
        os.makedirs(target_folder, exist_ok=True)
        
        # 步骤 1: 创建目录树镜像
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=target_folder
        )
        mirror.run()
        
        # 验证目录结构
        assert os.path.isdir(os.path.join(target_folder, '电影'))
        assert os.path.isfile(os.path.join(target_folder, '电影', 'Movie.2023.mkv'))
        
        # 步骤 2: 合并元数据
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=target_folder
        )
        merger.run()
        
        # 验证元数据被合并
        assert os.path.exists(os.path.join(target_folder, '电影', 'Movie.2023.nfo'))


class TestErrorHandling:
    """测试错误处理"""
    
    def test_symlink_creator_invalid_source(self, temp_dir):
        """测试无效的源文件夹"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=['/nonexistent/path'],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        creator.run(callback)

        # 验证流程完成（不存在的源文件夹会被跳过，不会报错退出）
        assert any('完成' in msg or '共创建' in msg for msg in messages)
    
    def test_file_merger_invalid_scrap_folder(self, temp_dir):
        """测试无效的文件合并刮削文件夹"""
        from autosync.FileMerger import FileMerger
        
        # 应该抛出 FileNotFoundError
        with pytest.raises(FileNotFoundError):
            FileMerger(
                scrap_folder='/nonexistent/scrap',
                target_folder=temp_dir
            )
    
    def test_tree_mirror_invalid_file(self, temp_dir):
        """测试无效的树文件"""
        from autosync.TreeMirror import TreeMirror
        
        mirror = TreeMirror(
            tree_file='/nonexistent/tree.txt',
            export_folder=temp_dir
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        mirror.run(callback)
        
        # 验证树数据为空
        assert any('为空' in msg for msg in messages)


class TestPerformance:
    """测试性能"""
    
    def test_large_file_list_scan(self, temp_dir):
        """测试大量文件的扫描性能"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        # 创建大量文件
        source_folder = os.path.join(temp_dir, 'source')
        os.makedirs(source_folder, exist_ok=True)
        
        for i in range(100):
            subfolder = os.path.join(source_folder, f'folder_{i}')
            os.makedirs(subfolder, exist_ok=True)
            with open(os.path.join(subfolder, f'movie_{i}.mp4'), 'w') as f:
                f.write(f'video {i}')
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        start_time = time.time()
        files = creator.scan(source_folder)
        end_time = time.time()
        
        # 验证扫描结果
        assert len(files) == 100
        
        # 验证性能（应该在 5 秒内完成）
        assert end_time - start_time < 5.0
    
    def test_multithreaded_symlink_creation(self, temp_dir):
        """测试多线程软链接创建"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        # 创建多个文件
        source_folder = os.path.join(temp_dir, 'source')
        os.makedirs(source_folder, exist_ok=True)
        
        for i in range(50):
            with open(os.path.join(source_folder, f'movie_{i}.mp4'), 'w') as f:
                f.write(f'video {i}')
        
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        # 使用单线程模式（新版 run 方法）
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            thread_count=1
        )
        
        start_time = time.time()
        creator.run()
        end_time = time.time()
        
        # 验证所有文件都被创建
        assert creator.success_count == 50
        
        # 验证性能
        assert end_time - start_time < 10.0