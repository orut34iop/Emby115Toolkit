"""
autosync.TreeMirror 模块单元测试
"""
import pytest
import os
import tempfile
import shutil


class TestTreeMirrorInit:
    """测试 TreeMirror 初始化"""
    
    def test_init_with_default_values(self, temp_dir):
        """测试使用默认值初始化"""
        from autosync.TreeMirror import TreeMirror
        
        mirror = TreeMirror(
            tree_file='tree.txt',
            export_folder=temp_dir
        )
        
        assert mirror.tree_file == 'tree.txt'
        assert mirror.export_folder == temp_dir
        assert mirror.fix_garbled_text == False
    
    def test_init_with_fix_garbled(self, temp_dir):
        """测试启用乱码修复"""
        from autosync.TreeMirror import TreeMirror
        
        mirror = TreeMirror(
            tree_file='tree.txt',
            export_folder=temp_dir,
            fix_garbled_text=True
        )
        
        assert mirror.fix_garbled_text == True


class TestTreeMirrorParseTree:
    """测试 parse_tree 方法"""
    
    def test_parse_simple_tree(self, temp_dir, sample_tree_content):
        """测试解析简单的目录树"""
        from autosync.TreeMirror import TreeMirror
        
        # 创建树文件
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(sample_tree_content)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        # 验证解析结果
        assert len(result) > 0
        assert all('name' in item and 'is_dir' in item and 'depth' in item for item in result)
    
    def test_parse_tree_with_garbled_text(self, temp_dir):
        """测试解析包含乱码的目录树"""
        from autosync.TreeMirror import TreeMirror
        
        tree_content = """我的资源
|——电影
| |- 动作片
| | |- Movie.*.2023.mkv
"""
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir,
            fix_garbled_text=True
        )
        
        result = mirror.parse_tree()
        
        # 验证乱码被修复
        names = [item['name'] for item in result]
        assert any('Movie.s.2023' in name for name in names)
    
    def test_parse_empty_tree_file(self, temp_dir):
        """测试解析空树文件"""
        from autosync.TreeMirror import TreeMirror
        
        tree_file = os.path.join(temp_dir, 'empty.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write('')
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        assert result == []
    
    def test_parse_tree_with_multiple_encodings(self, temp_dir):
        """测试解析不同编码的树文件"""
        from autosync.TreeMirror import TreeMirror
        
        # 测试 GBK 编码
        tree_content_gbk = """我的资源
|——电影
| |- 测试文件.txt
""".encode('gbk')
        
        tree_file = os.path.join(temp_dir, 'tree_gbk.txt')
        with open(tree_file, 'wb') as f:
            f.write(tree_content_gbk)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        # 验证能够正确解析
        assert len(result) > 0
        names = [item['name'] for item in result]
        assert any('测试文件' in name for name in names)


class TestTreeMirrorCreateStructure:
    """测试 create_structure 方法"""
    
    def test_create_simple_structure(self, temp_dir, sample_tree_content):
        """测试创建简单的目录结构"""
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
        
        # 解析并创建
        tree_data = mirror.parse_tree()
        mirror.create_structure(tree_data)
        
        # 验证目录结构
        assert os.path.isdir(os.path.join(export_folder, '电影'))
        assert os.path.isdir(os.path.join(export_folder, '电影', '动作片'))
        assert os.path.isdir(os.path.join(export_folder, '剧集', '美剧'))
        assert os.path.isdir(os.path.join(export_folder, '剧集', '美剧', 'Season 1'))
        
        # 验证空文件被创建
        assert os.path.isfile(os.path.join(export_folder, '电影', '动作片', 'Movie.A.2023.mkv'))
        assert os.path.isfile(os.path.join(export_folder, '剧集', '美剧', 'Season 1', 'Episode.01.mkv'))
    
    def test_create_structure_with_callback(self, temp_dir, sample_tree_content):
        """测试带回调的创建"""
        from autosync.TreeMirror import TreeMirror
        
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
        
        tree_data = mirror.parse_tree()
        mirror.create_structure(tree_data, callback)
        
        # 验证回调被调用
        assert len(messages) > 0
    
    def test_create_structure_preserves_existing(self, temp_dir, sample_tree_content):
        """测试保留现有文件"""
        from autosync.TreeMirror import TreeMirror
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(sample_tree_content)
        
        export_folder = os.path.join(temp_dir, 'export')
        os.makedirs(export_folder, exist_ok=True)
        
        # 预先创建一些文件
        existing_file = os.path.join(export_folder, '电影', '动作片', 'Movie.A.2023.mkv')
        os.makedirs(os.path.dirname(existing_file), exist_ok=True)
        with open(existing_file, 'w') as f:
            f.write('existing content')
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=export_folder
        )
        
        tree_data = mirror.parse_tree()
        mirror.create_structure(tree_data)
        
        # 验证现有文件未被覆盖
        with open(existing_file, 'r') as f:
            content = f.read()
        assert content == 'existing content'


class TestTreeMirrorRun:
    """测试 run 方法"""
    
    def test_run_complete_workflow(self, temp_dir, sample_tree_content):
        """测试完整工作流程"""
        from autosync.TreeMirror import TreeMirror
        
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
        
        # 验证回调消息
        assert len(messages) > 0
        assert any('完成' in msg for msg in messages)
        
        # 验证结构已创建
        assert os.path.isdir(os.path.join(export_folder, '电影'))
        assert os.path.isdir(os.path.join(export_folder, '剧集'))
    
    def test_run_with_stop_flag(self, temp_dir, sample_tree_content):
        """测试停止标志"""
        from autosync.TreeMirror import TreeMirror
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(sample_tree_content)
        
        export_folder = os.path.join(temp_dir, 'export')
        os.makedirs(export_folder, exist_ok=True)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=export_folder
        )
        
        # 设置停止标志
        mirror.stop_flag.set()
        
        messages = []
        
        def callback(msg):
            messages.append(msg)
        
        mirror.run(callback)
        
        # 验证被停止
        assert any('停止' in msg or '已停止' in msg for msg in messages)


class TestTreeMirrorEdgeCases:
    """测试边界情况"""
    
    def test_parse_tree_with_special_characters(self, temp_dir):
        """测试特殊字符处理"""
        from autosync.TreeMirror import TreeMirror
        
        tree_content = """我的资源
|——电影
| |- 文件[1].mkv
| |- 文件(2).mp4
| |- 文件&3.avi
"""
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        # 验证特殊字符被正确处理
        names = [item['name'] for item in result]
        assert any('文件[1]' in name for name in names)
        assert any('文件(2)' in name for name in names)
    
    def test_parse_tree_with_deep_nesting(self, temp_dir):
        """测试深层嵌套"""
        from autosync.TreeMirror import TreeMirror
        
        tree_content = """根目录
|——一级
| |- 二级
| | |- 三级
| | | |- 四级
| | | | |- 五级
| | | | | |- deep_file.txt
"""
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        # 验证深度
        depths = [item['depth'] for item in result]
        assert max(depths) >= 5
    
    def test_parse_tree_with_empty_lines(self, temp_dir):
        """测试包含空行的树文件"""
        from autosync.TreeMirror import TreeMirror
        
        tree_content = """我的资源

|——电影

| |- 动作片

| | |- Movie.mkv

"""
        
        tree_file = os.path.join(temp_dir, 'tree.txt')
        with open(tree_file, 'w', encoding='utf-8') as f:
            f.write(tree_content)
        
        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=temp_dir
        )
        
        result = mirror.parse_tree()
        
        # 验证空行被正确处理
        assert len(result) > 0
        names = [item['name'] for item in result]
        assert 'Movie.mkv' in names
