针对115网盘 + CloudDrive2 + Emby 优化的实用工具， 在Windows中运行， Linux/Mac系统未调试过

我的环境：

windows主机： 挂载CloudDrive2, 并运行Emby Server

atv： infuse播放器

针对115网盘封控做了优化
用这个工具协助导入115网盘中的多部影剧，并创建对应软链接
同时支持emby媒体库的几个常用功能， 自动多版本合并， 更新流派为中文， emby入库前的查询是否已经有相同的影剧

最实用的功能介绍: 115网盘中PB级别的海量影剧数据如何10分种生成所有软链接：
1. 在115官方浏览器中导出目录树
2. 在"115目录树镜像"中在PC本地生成文件树镜像（全部都是空文件）
3. 在"导出软链接"页选择上一步在pc本地创建的文件树镜像, 同时勾选上"软链接路径替换设置"，并填写对应的替换路径， 然后点击创建软链接， 就能快速创建所有的软链接文件

具体功能说明后续更新

how to run :  python main.py

致谢： 项目中使用了shenxianmq的MediaHelper项目（https://github.com/shenxianmq/MediaHelper）的部分代码，感谢shenxianmq!
