import os
import sys
import yaml

class Config:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化配置"""
        # 获取程序根目录
        """
        根据当前是否为打包后的EXE文件来决定配置文件的保存位置。
        如果是EXE，则返回EXE所在的目录；如果是Python脚本，则返回脚本所在的目录。
        """
        if getattr(sys, 'frozen', False):
            # 打包成EXE的情况
            self.config_dir = os.path.dirname(sys.executable)
        else:
            # Python脚本的情况
            self.config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.config_file = os.path.join(self.config_dir, 'config.yaml')
        
        # 确保配置文件存在
        if not os.path.exists(self.config_file):
            self._create_default_config()
            
        # 加载配置
        self._load_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            'export_symlink': {
                'link_suffixes': ['.mkv', '.iso', '.ts', '.mp4', '.avi', '.rmvb', 
                                '.wmv', '.m2ts', '.mpg', '.flv', '.rm'],
                'meta_suffixes': ['.nfo', '.jpg', '.png', '.svg', '.ass', '.srt', '.sup'],
                'thread_count': 4,
                'link_folders': [],
                'target_folder': ''
            }
        }
    
    def _create_default_config(self):
        """创建默认配置文件"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self._get_default_config(), f, allow_unicode=True, sort_keys=False)
    
    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
            
            # 获取默认配置
            default_config = self._get_default_config()
            
            # 确保配置不为空
            if not loaded_config:
                loaded_config = {}
            
            # 递归合并配置，确保所有默认值都存在
            def merge_config(default, loaded):
                if not isinstance(default, dict):
                    return loaded if loaded is not None else default
                
                result = loaded.copy() if loaded else {}
                for key, value in default.items():
                    if key not in result:
                        result[key] = value
                    else:
                        result[key] = merge_config(value, result.get(key))
                return result
            
            self._config = merge_config(default_config, loaded_config)
            
            # 保存合并后的配置
            self.save()
            
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
            self._create_default_config()
    
    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self._config, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, section, key=None, default=None):
        """获取配置值
        
        Args:
            section: 配置区段名
            key: 配置键名，如果为None则返回整个区段
            default: 默认值，当配置不存在时返回
        """
        if section not in self._config:
            return default
        
        if key is None:
            return self._config[section]
        
        return self._config[section].get(key, default)
    
    def set(self, section, key, value):
        """设置配置值
        
        Args:
            section: 配置区段名
            key: 配置键名
            value: 配置值
        """
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section][key] = value
