"""
autosync.SymlinkCreator 模块单元测试
"""
import pytest
import os
import tempfile
import shutil
import threading
import logging


class TestSymlinkCreatorInit:
    """测试 SymlinkCreator 初始化"""
    
    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        assert creator.link_folders == [temp_dir]
        assert creator.target_folder == temp_dir
        assert creator.symlink_mode == 'symlink'
        assert creator.thread_count == 4  # 默认值
        assert creator.enable_replace_path == False
        assert creator.original_path == ''
        assert creator.replace_path == ''
        assert creator.only_tvshow_nfo == True
    
    def test_init_with_custom_values(self, temp_dir):
        """测试使用自定义值初始化"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=[temp_dir, '/another/path'],
            target_folder=temp_dir,
            symlink_mode='strm',
            thread_count=8,
            enable_replace_path=True,
            original_path='/original',
            replace_path='/replacement',
            only_tvshow_nfo=False
        )
        
        assert creator.symlink_mode == 'strm'
        assert creator.thread_count == 8
        assert creator.enable_replace_path == True
        assert creator.original_path == '/original'
        assert creator.replace_path == '/replacement'
        assert creator.only_tvshow_nfo == False
    
    def test_init_invalid_symlink_mode(self, temp_dir):
        """测试无效的 symlink_mode"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        with pytest.raises(ValueError):
            SymlinkCreator(
                link_folders=[temp_dir],
                target_folder=temp_dir,
                symlink_mode='invalid_mode'
            )

    def test_init_with_115_protect_options(self, temp_dir):
        """测试 PyQt5 防封配置参数可被后端接收"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator

        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            enable_115_protect=True,
            op_interval_sec=4,
        )

        assert creator.enable_115_protect is True
        assert creator.op_interval_sec == 4


class TestSymlinkCreatorScan:
    """测试 scan 方法"""
    
    def test_scan_empty_folder(self, temp_dir):
        """测试扫描空文件夹"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        result = creator.scan(temp_dir)
        
        assert result == []
    
    def test_scan_with_video_files(self, temp_dir, create_test_file_structure):
        """测试扫描包含视频文件的文件夹"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'movies/movie1.mp4': 'video1',
            'movies/movie2.mkv': 'video2',
            'movies/poster.jpg': 'image',
            'movies/movie.nfo': 'metadata',
        }
        create_test_file_structure(structure)
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        result = creator.scan(os.path.join(temp_dir, 'movies'))
        
        # 软链接流程只处理配置的视频后缀，元数据由 MetadataCopyer 负责
        assert len(result) == 2
        names = [item['name'] for item in result]
        assert 'movie1.mp4' in names
        assert 'movie2.mkv' in names
        assert 'poster.jpg' not in names
        assert 'movie.nfo' not in names
    
    def test_scan_with_subfolders(self, temp_dir, create_test_file_structure):
        """测试扫描包含子文件夹的目录"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'tvshow/Season 1/episode01.mp4': 'ep1',
            'tvshow/Season 1/episode02.mp4': 'ep2',
            'tvshow/Season 2/episode01.mp4': 'ep3',
            'tvshow/tvshow.nfo': 'show metadata',
        }
        create_test_file_structure(structure)
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        result = creator.scan(os.path.join(temp_dir, 'tvshow'))
        
        # 只匹配视频文件，tvshow.nfo 不属于软链接创建流程
        assert len(result) == 3
    
    def test_scan_with_symlinks(self, temp_dir, create_test_file_structure):
        """测试扫描时跳过符号链接"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        # 创建源文件
        structure = {
            'source/real_file.mp4': 'real video',
        }
        create_test_file_structure(structure)
        
        # 创建符号链接
        os.symlink(
            os.path.join(temp_dir, 'source', 'real_file.mp4'),
            os.path.join(temp_dir, 'source', 'link_file.mp4')
        )
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        result = creator.scan(os.path.join(temp_dir, 'source'))
        
        # 应该只找到真实文件，跳过符号链接
        assert len(result) == 1
        assert result[0]['name'] == 'real_file.mp4'


class TestSymlinkCreatorCreate:
    """测试 create 方法"""
    
    def test_create_symlink(self, temp_dir, create_test_file_structure):
        """测试创建符号链接"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie.mp4': 'video content',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证符号链接已创建
        link_path = os.path.join(target_folder, 'movie.mp4')
        assert os.path.islink(link_path)
        assert os.path.exists(link_path)

    def test_create_skips_non_video_metadata_files(self, temp_dir, create_test_file_structure):
        """测试软链接流程只处理视频后缀"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator

        structure = {
            'source/movie.mp4': 'video content',
            'source/movie.nfo': 'metadata',
            'source/poster.jpg': 'image',
        }
        create_test_file_structure(structure)

        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )

        creator.run()

        assert os.path.islink(os.path.join(target_folder, 'movie.mp4'))
        assert not os.path.exists(os.path.join(target_folder, 'movie.nfo'))
        assert not os.path.exists(os.path.join(target_folder, 'poster.jpg'))
        assert creator.scanned_files == 3
        assert creator.matched_files == 1

    def test_create_skips_existing_broken_symlink(self, temp_dir, create_test_file_structure):
        """测试损坏符号链接也按已存在目标处理"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator

        structure = {
            'source/movie.mp4': 'video content',
        }
        create_test_file_structure(structure)

        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        broken_target = os.path.join(target_folder, 'movie.mp4')
        os.symlink(os.path.join(temp_dir, 'missing.mp4'), broken_target)

        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )

        creator.run()

        assert os.path.islink(broken_target)
        assert creator.existing_links == 1
        assert creator.error_count == 0
    
    def test_create_strm_file(self, temp_dir, create_test_file_structure):
        """测试创建 strm 文件"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie.mp4': 'video content',
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
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证 strm 文件已创建
        strm_path = os.path.join(target_folder, 'movie.strm')
        assert os.path.exists(strm_path)
        
        # 验证内容
        with open(strm_path, 'r') as f:
            content = f.read().strip()
        assert content == os.path.join(source_folder, 'movie.mp4')
    
    def test_create_with_path_replacement(self, temp_dir, create_test_file_structure):
        """测试路径替换功能"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie.mp4': 'video content',
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
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证路径替换
        strm_path = os.path.join(target_folder, 'movie.strm')
        with open(strm_path, 'r') as f:
            content = f.read().strip()
        assert content.startswith('/mnt/media')
        assert 'movie.mp4' in content
    
    def test_create_preserves_directory_structure(self, temp_dir, create_test_file_structure):
        """测试保持目录结构"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/Season 1/episode01.mp4': 'ep1',
            'source/Season 2/episode01.mp4': 'ep2',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证目录结构被保留
        assert os.path.islink(os.path.join(target_folder, 'Season 1', 'episode01.mp4'))
        assert os.path.islink(os.path.join(target_folder, 'Season 2', 'episode01.mp4'))


class TestSymlinkCreatorOnlyTvshowNfo:
    """测试 only_tvshow_nfo 选项"""
    
    def test_only_tvshow_nfo_true(self, temp_dir, create_test_file_structure):
        """测试只复制 tvshow.nfo"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/tvshow/tvshow.nfo': 'show metadata',
            'source/tvshow/Season 1/episode01.nfo': 'episode metadata',
            'source/tvshow/Season 1/episode01.mp4': 'video',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source', 'tvshow')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            only_tvshow_nfo=True
        )
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证 nfo 不由软链接流程处理
        assert not os.path.exists(os.path.join(target_folder, 'tvshow.nfo'))
        assert not os.path.exists(os.path.join(target_folder, 'Season 1', 'episode01.nfo'))
        assert os.path.islink(os.path.join(target_folder, 'Season 1', 'episode01.mp4'))
    
    def test_only_tvshow_nfo_false(self, temp_dir, create_test_file_structure):
        """测试复制所有 nfo 文件"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/tvshow/tvshow.nfo': 'show metadata',
            'source/tvshow/Season 1/episode01.nfo': 'episode metadata',
            'source/tvshow/Season 1/episode01.mp4': 'video',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source', 'tvshow')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            only_tvshow_nfo=False
        )
        
        # 扫描并创建
        files = creator.scan(source_folder)
        creator.create(files, target_folder)
        
        # 验证 nfo 不由软链接流程处理
        assert not os.path.exists(os.path.join(target_folder, 'tvshow.nfo'))
        assert not os.path.exists(os.path.join(target_folder, 'Season 1', 'episode01.nfo'))
        assert os.path.islink(os.path.join(target_folder, 'Season 1', 'episode01.mp4'))


class TestSymlinkCreatorCallback:
    """测试回调功能"""
    
    def test_run_with_callback(self, temp_dir, create_test_file_structure):
        """测试带回调的运行"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie1.mp4': 'video1',
            'source/movie2.mp4': 'video2',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            thread_count=1
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        # 运行
        creator.run(callback)
        
        # 验证回调被调用
        assert len(messages) > 0
        assert any('完成' in msg or '软链接' in msg for msg in messages)
    
    def test_stop_flag(self, temp_dir, create_test_file_structure):
        """测试停止标志"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie1.mp4': 'video1',
            'source/movie2.mp4': 'video2',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink'
        )
        
        # 设置停止标志
        creator.stop_flag.set()
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        # 运行（应该立即停止）
        creator.run(callback)
        
        # 验证被停止
        assert any('停止' in msg or '已停止' in msg for msg in messages)

    def test_run_logs_scan_and_create_progress(self, temp_dir, create_test_file_structure, caplog):
        """测试运行时输出扫描和创建进度，便于 GUI 判断后台仍在工作"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator

        structure = {
            'source/movie1.mp4': 'video1',
            'source/movie2.mp4': 'video2',
            'source/poster.jpg': 'image',
        }
        create_test_file_structure(structure)

        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)

        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            progress_interval=1,
        )

        with caplog.at_level(logging.INFO):
            creator.run()

        messages = "\n".join(record.getMessage() for record in caplog.records)
        assert "扫描进度:" in messages
        assert "创建进度:" in messages


class TestSymlinkCreatorCounters:
    """测试计数器功能"""
    
    def test_counters_initialization(self, temp_dir):
        """测试计数器初始化"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        assert creator.total_files == 0
        assert creator.processed_files == 0
        assert creator.success_count == 0
        assert creator.error_count == 0
    
    def test_counters_after_run(self, temp_dir, create_test_file_structure):
        """测试运行后的计数器"""
        from emby115_v1.autosync.SymlinkCreator import SymlinkCreator
        
        structure = {
            'source/movie1.mp4': 'video1',
            'source/movie2.mp4': 'video2',
            'source/movie3.mp4': 'video3',
        }
        create_test_file_structure(structure)
        
        source_folder = os.path.join(temp_dir, 'source')
        target_folder = os.path.join(temp_dir, 'target')
        os.makedirs(target_folder, exist_ok=True)
        
        creator = SymlinkCreator(
            link_folders=[source_folder],
            target_folder=target_folder,
            symlink_mode='symlink',
            thread_count=1
        )
        
        creator.run()
        
        # 验证计数器
        assert creator.total_files == 3
        assert creator.processed_files == 3
        assert creator.success_count == 3
        assert creator.error_count == 0
