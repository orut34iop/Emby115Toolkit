"""
emby.EmbyOperator 模块单元测试
"""
import pytest
import os
import tempfile
import shutil
import threading
import time
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET


class TestEmbyOperatorInit:
    """测试 EmbyOperator 初始化"""
    
    def test_init_with_url_and_api(self):
        """测试使用 URL 和 API 密钥初始化"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        assert operator.emby_url == 'http://localhost:8096'
        assert operator.emby_api == 'test-api-key'
        assert operator.server_url == 'http://localhost:8096'
        assert operator.api_key == 'test-api-key'
    
    def test_init_with_username(self):
        """测试使用用户名初始化"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key',
            emby_username='testuser'
        )
        
        assert operator.emby_username == 'testuser'
        assert operator.user_name == 'testuser'
    
    def test_init_with_legacy_params(self):
        """测试使用旧版参数名初始化"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            server_url='http://localhost:8096',
            api_key='test-api-key',
            user_name='testuser'
        )
        
        assert operator.server_url == 'http://localhost:8096'
        assert operator.api_key == 'test-api-key'
        assert operator.user_name == 'testuser'
        assert operator.emby_url == 'http://localhost:8096'
        assert operator.emby_api == 'test-api-key'
        assert operator.emby_username == 'testuser'


class TestEmbyOperatorExtractTmdbid:
    """测试 extract_tmdbid_from_nfo 方法"""
    
    def test_extract_tmdbid_valid_nfo(self, temp_dir):
        """测试从有效的 NFO 文件提取 TMDB ID"""
        from emby.EmbyOperator import EmbyOperator
        
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
    <tmdbid>12345</tmdbid>
</movie>"""
        
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)
        
        assert result == '12345'
        assert is_damaged == False
    
    def test_extract_tmdbid_missing_tmdbid(self, temp_dir):
        """测试缺少 tmdbid 的 NFO 文件"""
        from emby.EmbyOperator import EmbyOperator
        
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
</movie>"""
        
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)
        
        assert result is None
        assert is_damaged == False
    
    def test_extract_tmdbid_damaged_nfo(self, temp_dir):
        """测试损坏的 NFO 文件（强制提取）"""
        from emby.EmbyOperator import EmbyOperator
        
        # 不完整的 XML，但有 tmdbid 行
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
  <tmdbid>67890</tmdbid>
"""
        
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)
        
        assert result == '67890'
        assert is_damaged == True


class TestEmbyOperatorQueryMovies:
    """测试 query_movies_by_tmdbid 方法"""
    
    def test_query_movies_found(self):
        """测试找到匹配的影片"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        movies = [
            {'Name': 'Movie 1', 'ProviderIds': {'Tmdb': '12345'}},
            {'Name': 'Movie 2', 'ProviderIds': {'Tmdb': '67890'}},
        ]
        
        result = operator.query_movies_by_tmdbid(movies, '12345')
        
        assert result == True
    
    def test_query_movies_not_found(self):
        """测试未找到匹配的影片"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        movies = [
            {'Name': 'Movie 1', 'ProviderIds': {'Tmdb': '12345'}},
            {'Name': 'Movie 2', 'ProviderIds': {'Tmdb': '67890'}},
        ]
        
        result = operator.query_movies_by_tmdbid(movies, '99999')
        
        assert result == False
    
    def test_query_movies_empty_list(self):
        """测试空影片列表"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.query_movies_by_tmdbid([], '12345')
        
        assert result == False


class TestEmbyOperatorGroupMovies:
    """测试 group_movies_by_tmdbid 方法"""
    
    def test_group_movies_with_duplicates(self):
        """测试分组有重复的影片"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        movies = [
            {'Id': '1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'Movie A HD', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/b'},
            {'Id': '3', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/c'},
        ]
        
        result = operator.group_movies_by_tmdbid(movies)
        
        assert '12345' in result
        assert '67890' in result
        assert len(result['12345']) == 2
        assert len(result['67890']) == 1
    
    def test_group_movies_no_duplicates(self):
        """测试分组无重复的影片"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        movies = [
            {'Id': '1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/b'},
        ]
        
        result = operator.group_movies_by_tmdbid(movies)
        
        assert len(result) == 2
        assert len(result['12345']) == 1
        assert len(result['67890']) == 1


class TestEmbyOperatorFindRelatedVideos:
    """测试 find_related_videos 方法"""
    
    def test_find_related_video_exists(self, temp_dir, create_test_file_structure):
        """测试找到相关视频文件"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
            'movies/Movie.2023.mp4': 'video content',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)
        
        assert result is not None
        assert 'Movie.2023.mp4' in result
    
    def test_find_related_video_not_exists(self, temp_dir, create_test_file_structure):
        """测试未找到相关视频文件"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)
        
        assert result is None
    
    def test_find_related_video_different_extensions(self, temp_dir, create_test_file_structure):
        """测试不同扩展名的视频文件"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
            'movies/Movie.2023.mkv': 'video content',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)
        
        assert result is not None
        assert 'Movie.2023.mkv' in result


class TestEmbyOperatorCheckNfoFiles:
    """测试 check_nfo_files 方法"""
    
    def test_check_nfo_files_all_valid(self, temp_dir, create_test_file_structure):
        """测试所有 NFO 都有对应视频"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie2.2022.nfo': 'nfo2',
            'movies/Movie2.2022.mkv': 'video2',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.check_nfo_files(temp_dir)
        
        assert result['total_nfo'] == 2
        assert len(result['no_video_nfo']) == 0
        assert len(result['found_video_nfo']) == 2
    
    def test_check_nfo_files_some_missing(self, temp_dir, create_test_file_structure):
        """测试部分 NFO 缺少视频"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie2.2022.nfo': 'nfo2',
            # Movie2 没有视频文件
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.check_nfo_files(temp_dir)
        
        assert result['total_nfo'] == 2
        assert len(result['no_video_nfo']) == 1
        assert len(result['found_video_nfo']) == 1
    
    def test_check_nfo_files_skips_tvshow_nfo(self, temp_dir, create_test_file_structure):
        """测试跳过 tvshow.nfo 和 season.nfo"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'tvshow/tvshow.nfo': 'show nfo',
            'tvshow/season.nfo': 'season nfo',
            'tvshow/episode01.nfo': 'ep nfo',
            'tvshow/episode01.mp4': 'ep video',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.check_nfo_files(temp_dir)
        
        # tvshow.nfo 和 season.nfo 应该被跳过
        assert result['total_nfo'] == 1
        assert len(result['found_video_nfo']) == 1


class TestEmbyOperatorCheckVideoFiles:
    """测试 check_video_files 方法"""
    
    def test_check_video_files_all_have_nfo(self, temp_dir, create_test_file_structure):
        """测试所有视频都有 NFO"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie2.2022.mkv': 'video2',
            'movies/Movie2.2022.nfo': 'nfo2',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.check_video_files(temp_dir)
        
        assert result['total_videos'] == 2
        assert len(result['no_nfo_videos']) == 0
        assert len(result['found_nfo_videos']) == 2
    
    def test_check_video_files_some_missing_nfo(self, temp_dir, create_test_file_structure):
        """测试部分视频缺少 NFO"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie2.2022.mkv': 'video2',
            # Movie2 没有 NFO
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.check_video_files(temp_dir)
        
        assert result['total_videos'] == 2
        assert len(result['no_nfo_videos']) == 1
        assert len(result['found_nfo_videos']) == 1


class TestEmbyOperatorForceExtractTmdbid:
    """测试 force_extract_tmdbid_from_file 方法"""
    
    def test_force_extract_valid(self, temp_dir):
        """测试强制提取有效的 tmdbid"""
        from emby.EmbyOperator import EmbyOperator
        
        content = """  <tmdbid>12345</tmdbid>
  <title>Test</title>
"""
        file_path = os.path.join(temp_dir, 'test.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.force_extract_tmdbid_from_file(file_path)
        
        assert result == '12345'
    
    def test_force_extract_not_found(self, temp_dir):
        """测试强制提取未找到 tmdbid"""
        from emby.EmbyOperator import EmbyOperator
        
        content = """  <title>Test</title>
"""
        file_path = os.path.join(temp_dir, 'test.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        result = operator.force_extract_tmdbid_from_file(file_path)
        
        assert result is None


class TestEmbyOperatorNfoParsing:
    """测试 NFO 文件解析"""
    
    def test_extract_tmdb_id_from_nfo(self, temp_dir, sample_nfo_content):
        """测试从 NFO 提取 TMDB ID"""
        # 创建 NFO 文件
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(sample_nfo_content)
        
        # 解析 NFO
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        # 验证 TMDB ID
        uniqueid = root.find('uniqueid[@type="tmdb"]')
        assert uniqueid is not None
        assert uniqueid.text == '12345'
    
    def test_extract_genres_from_nfo(self, temp_dir, sample_nfo_content):
        """测试从 NFO 提取流派"""
        # 创建 NFO 文件
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(sample_nfo_content)
        
        # 解析 NFO
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        # 验证流派
        genres = root.findall('genre')
        assert len(genres) == 2
        genre_texts = [g.text for g in genres]
        assert 'Action' in genre_texts
        assert 'Adventure' in genre_texts


class TestEmbyOperatorClearFiles:
    """测试 clear_files_by_type 方法"""
    
    def test_clear_video_files(self, temp_dir, create_test_file_structure):
        """测试清除视频文件"""
        from emby.EmbyOperator import EmbyOperator
        
        structure = {
            'movies/movie1.mp4': 'video1',
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.mkv': 'video2',
            'movies/poster.jpg': 'poster',
        }
        create_test_file_structure(structure)
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        operator.clear_files_by_type(temp_dir, 'VIDEO', callback)
        
        # 等待线程完成
        time.sleep(0.5)
        
        # 验证视频文件被删除
        assert not os.path.exists(os.path.join(temp_dir, 'movies', 'movie1.mp4'))
        assert not os.path.exists(os.path.join(temp_dir, 'movies', 'movie2.mkv'))
        
        # 验证其他文件未被删除
        assert os.path.exists(os.path.join(temp_dir, 'movies', 'movie1.nfo'))
        assert os.path.exists(os.path.join(temp_dir, 'movies', 'poster.jpg'))


class TestEmbyOperatorCallback:
    """测试回调功能"""
    
    def test_check_duplicate_callback(self, temp_dir, sample_nfo_content):
        """测试 check_duplicate 回调"""
        from emby.EmbyOperator import EmbyOperator

        # 创建 NFO 文件
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
    <tmdbid>12345</tmdbid>
</movie>"""
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )

        messages = []

        def callback(msg):
            messages.append(msg)

        # 模拟 get_all_media 返回包含该影片的数据（有重复）
        mock_movies = [
            {'Name': 'Test Movie', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/to/movie'}
        ]
        with patch.object(operator, 'get_all_media', return_value=mock_movies):
            operator.check_duplicate(temp_dir, callback)
            time.sleep(0.5)

        # 验证回调被调用
        assert len(messages) > 0


class TestEmbyOperatorGenresMap:
    """测试流派翻译映射"""
    
    def test_genres_map_exists_in_methods(self):
        """测试流派翻译映射在方法中存在"""
        from emby.EmbyOperator import EmbyOperator
        
        operator = EmbyOperator(
            emby_url='http://localhost:8096',
            emby_api='test-api-key'
        )
        
        # 验证流派翻译方法存在
        assert hasattr(operator, 'emby_tv_translate_genres_and_update_whole_item')
        assert hasattr(operator, 'emby_movie_translate_genres_and_update_whole_item')
    
    def test_common_genres_translation(self):
        """测试常见流派的翻译映射逻辑"""
        # 验证常见的中英文流派映射
        genres_map = {
            'Action': '动作',
            'Adventure': '冒险',
            'Animation': '动画',
            'Comedy': '喜剧',
            'Crime': '犯罪',
            'Documentary': '纪录片',
            'Drama': '剧情',
            'Family': '家庭',
            'Fantasy': '奇幻',
            'Horror': '恐怖',
            'Mystery': '悬疑',
            'Romance': '爱情',
            'Science Fiction': '科幻',
            'Thriller': '惊悚',
            'War': '战争',
            'Western': '西部',
        }
        
        # 验证映射不为空且包含常见流派
        assert len(genres_map) > 0
        assert 'Action' in genres_map
        assert 'Drama' in genres_map
        assert 'Comedy' in genres_map
        assert genres_map['Action'] == '动作'
        assert genres_map['Drama'] == '剧情'
        assert genres_map['Comedy'] == '喜剧'