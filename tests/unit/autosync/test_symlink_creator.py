"""
autosync.SymlinkCreator 模块单元测试
"""
import pytest
import os
import tempfile
import shutil
import threading


class TestSymlinkCreatorInit:
    """测试 SymlinkCreator 初始化"""
    
    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
        with pytest.raises(ValueError):
            SymlinkCreator(
                link_folders=[temp_dir],
                target_folder=temp_dir,
                symlink_mode='invalid_mode'
            )


class TestSymlinkCreatorScan:
    """测试 scan 方法"""
    
    def test_scan_empty_folder(self, temp_dir):
        """测试扫描空文件夹"""
        from autosync.SymlinkCreator import SymlinkCreator
        
        creator = SymlinkCreator(
            link_folders=[temp_dir],
            target_folder=temp_dir,
            symlink_mode='symlink'
        )
        
        result = creator.scan(temp_dir)
        
        assert result == []
    
    def test_scan_with_video_files(self, temp_dir, create_test_file_structure):
        """测试扫描包含视频文件的文件夹"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        
        # 应该找到视频文件和元数据文件
        assert len(result) == 4
        names = [item['name'] for item in result]
        assert 'movie1.mp4' in names
        assert 'movie2.mkv' in names
        assert 'poster.jpg' in names
        assert 'movie.nfo' in names
    
    def test_scan_with_subfolders(self, temp_dir, create_test_file_structure):
        """测试扫描包含子文件夹的目录"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        
        # 应该递归找到所有文件
        assert len(result) == 4
    
    def test_scan_with_symlinks(self, temp_dir, create_test_file_structure):
        """测试扫描时跳过符号链接"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
    
    def test_create_strm_file(self, temp_dir, create_test_file_structure):
        """测试创建 strm 文件"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        
        # 验证只有 tvshow.nfo 被创建
        assert os.path.islink(os.path.join(target_folder, 'tvshow.nfo'))
        assert not os.path.exists(os.path.join(target_folder, 'Season 1', 'episode01.nfo'))
        assert os.path.islink(os.path.join(target_folder, 'Season 1', 'episode01.mp4'))
    
    def test_only_tvshow_nfo_false(self, temp_dir, create_test_file_structure):
        """测试复制所有 nfo 文件"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        
        # 验证所有 nfo 文件都被创建
        assert os.path.islink(os.path.join(target_folder, 'tvshow.nfo'))
        assert os.path.islink(os.path.join(target_folder, 'Season 1', 'episode01.nfo'))


class TestSymlinkCreatorCallback:
    """测试回调功能"""
    
    def test_run_with_callback(self, temp_dir, create_test_file_structure):
        """测试带回调的运行"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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


class TestSymlinkCreatorCounters:
    """测试计数器功能"""
    
    def test_counters_initialization(self, temp_dir):
        """测试计数器初始化"""
        from autosync.SymlinkCreator import SymlinkCreator
        
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
        from autosync.SymlinkCreator import SymlinkCreator
        
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
