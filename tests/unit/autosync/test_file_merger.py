"""
autosync.FileMerger 模块单元测试
"""
import pytest
import os
import tempfile
import shutil
import sys


class TestFileMergerInit:
    """测试 FileMerger 初始化"""
    
    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.FileMerger import FileMerger
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir
        )
        
        assert merger.scrap_folder == temp_dir
        assert merger.target_folder == temp_dir
        assert merger.thread_count == 4
    
    def test_init_with_custom_thread_count(self, temp_dir):
        """测试自定义线程数"""
        from autosync.FileMerger import FileMerger
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir,
            thread_count=8
        )
        
        assert merger.thread_count == 8


class TestFileMergerScan:
    """测试 scan 方法"""
    
    def test_scan_empty_folder(self, temp_dir):
        """测试扫描空文件夹"""
        from autosync.FileMerger import FileMerger
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir
        )
        
        result = merger.scan(temp_dir)
        
        assert result == []
    
    def test_scan_with_files(self, temp_dir, create_test_file_structure):
        """测试扫描包含文件的文件夹"""
        from autosync.FileMerger import FileMerger
        
        structure = {
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.nfo': 'nfo2',
            'movies/poster.jpg': 'poster',
        }
        create_test_file_structure(structure)
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir
        )
        
        result = merger.scan(os.path.join(temp_dir, 'movies'))
        
        assert len(result) == 3
        names = [item['name'] for item in result]
        assert 'movie1.nfo' in names
        assert 'movie2.nfo' in names
        assert 'poster.jpg' in names
    
    def test_scan_with_subfolders(self, temp_dir, create_test_file_structure):
        """测试扫描包含子文件夹的目录"""
        from autosync.FileMerger import FileMerger
        
        structure = {
            'tvshow/Season 1/episode01.nfo': 'ep1',
            'tvshow/Season 1/episode02.nfo': 'ep2',
            'tvshow/tvshow.nfo': 'show metadata',
        }
        create_test_file_structure(structure)
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir
        )
        
        result = merger.scan(os.path.join(temp_dir, 'tvshow'))
        
        assert len(result) == 3


class TestFileMergerMatch:
    """测试 match 方法"""
    
    def test_match_identical_names(self, temp_dir, create_test_file_structure):
        """测试完全匹配的文件名"""
        from autosync.FileMerger import FileMerger
        
        # 创建刮削文件夹
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'nfo content',
            'scrap/Movie.2023.jpg': 'poster',
        }
        create_test_file_structure(scrap_structure)
        
        # 创建视频文件夹
        target_structure = {
            'target/Movie.2023.mp4': 'video content',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        # 扫描
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        
        # 匹配
        matches = merger.match(scrap_files, target_files)
        
        # 验证匹配结果
        assert len(matches) > 0
        # Movie.2023 应该匹配
        assert any('Movie.2023' in match[0]['name'] for match in matches)
    
    def test_match_no_matches(self, temp_dir, create_test_file_structure):
        """测试无匹配的情况"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Different.Name.nfo': 'nfo content',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Another.Name.mp4': 'video content',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        
        matches = merger.match(scrap_files, target_files)
        
        assert len(matches) == 0
    
    def test_match_multiple_files_same_name(self, temp_dir, create_test_file_structure):
        """测试同名多文件匹配"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'nfo',
            'scrap/Movie.2023.jpg': 'poster',
            'scrap/Movie.2023.srt': 'subtitle',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie.2023.mp4': 'video',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        
        matches = merger.match(scrap_files, target_files)
        
        # 所有三个文件都应该匹配到同一个视频
        assert len(matches) == 3


class TestFileMergerMerge:
    """测试 merge 方法"""
    
    def test_merge_single_file(self, temp_dir, create_test_file_structure):
        """测试合并单个文件"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'nfo content',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie.2023.mp4': 'video content',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        # 扫描和匹配
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        matches = merger.match(scrap_files, target_files)
        
        # 合并
        merger.merge(matches)
        
        # 验证文件被移动
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie.2023.nfo'))
        assert not os.path.exists(os.path.join(temp_dir, 'scrap', 'Movie.2023.nfo'))
    
    def test_merge_preserves_directory_structure(self, temp_dir, create_test_file_structure):
        """测试保持目录结构"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Season 1/episode01.nfo': 'ep1 nfo',
            'scrap/Season 1/episode01.jpg': 'ep1 poster',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Season 1/episode01.mp4': 'ep1 video',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        matches = merger.match(scrap_files, target_files)
        
        merger.merge(matches)
        
        # 验证文件被移动到正确的子目录
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Season 1', 'episode01.nfo'))
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Season 1', 'episode01.jpg'))
    
    def test_merge_skips_existing_files(self, temp_dir, create_test_file_structure):
        """测试跳过已存在的文件"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie.2023.nfo': 'new nfo content',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie.2023.mp4': 'video',
            'target/Movie.2023.nfo': 'existing nfo content',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        scrap_files = merger.scan(os.path.join(temp_dir, 'scrap'))
        target_files = merger.scan(os.path.join(temp_dir, 'target'))
        matches = merger.match(scrap_files, target_files)
        
        merger.merge(matches)
        
        # 验证现有文件未被覆盖
        with open(os.path.join(temp_dir, 'target', 'Movie.2023.nfo'), 'r') as f:
            content = f.read()
        assert content == 'existing nfo content'
        # 源文件应该仍然存在（因为跳过了）
        assert os.path.exists(os.path.join(temp_dir, 'scrap', 'Movie.2023.nfo'))


class TestFileMergerRun:
    """测试 run 方法"""
    
    def test_run_complete_workflow(self, temp_dir, create_test_file_structure):
        """测试完整工作流程"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie1.2023.nfo': 'nfo1',
            'scrap/Movie2.2022.nfo': 'nfo2',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie1.2023.mp4': 'video1',
            'target/Movie2.2022.mp4': 'video2',
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
        
        # 验证回调被调用
        assert len(messages) > 0
        
        # 验证文件被移动
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie1.2023.nfo'))
        assert os.path.exists(os.path.join(temp_dir, 'target', 'Movie2.2022.nfo'))
    
    def test_run_with_stop_flag(self, temp_dir, create_test_file_structure):
        """测试停止标志"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie1.2023.nfo': 'nfo1',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie1.2023.mp4': 'video1',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target')
        )
        
        # 设置停止标志
        merger.stop_flag.set()
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        merger.run(callback)
        
        # 验证被停止
        assert any('停止' in msg or '已停止' in msg for msg in messages)


class TestFileMergerCounters:
    """测试计数器功能"""
    
    def test_counters_initialization(self, temp_dir):
        """测试计数器初始化"""
        from autosync.FileMerger import FileMerger
        
        merger = FileMerger(
            scrap_folder=temp_dir,
            target_folder=temp_dir
        )
        
        assert merger.total_files == 0
        assert merger.processed_files == 0
        assert merger.success_count == 0
        assert merger.error_count == 0
    
    def test_counters_after_run(self, temp_dir, create_test_file_structure):
        """测试运行后的计数器"""
        from autosync.FileMerger import FileMerger
        
        scrap_structure = {
            'scrap/Movie1.nfo': 'nfo1',
            'scrap/Movie2.nfo': 'nfo2',
            'scrap/Movie3.nfo': 'nfo3',
        }
        create_test_file_structure(scrap_structure)
        
        target_structure = {
            'target/Movie1.mp4': 'video1',
            'target/Movie2.mp4': 'video2',
            'target/Movie3.mp4': 'video3',
        }
        create_test_file_structure(target_structure)
        
        merger = FileMerger(
            scrap_folder=os.path.join(temp_dir, 'scrap'),
            target_folder=os.path.join(temp_dir, 'target'),
            thread_count=1
        )
        
        merger.run()
        
        # 验证计数器
        assert merger.total_files == 3
        assert merger.processed_files == 3
        assert merger.success_count == 3
        assert merger.error_count == 0
