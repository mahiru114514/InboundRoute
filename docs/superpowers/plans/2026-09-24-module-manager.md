# 可视化模块管理 Implementation Plan

**Goal:** 在本机通过网页安装、配置、启停和卸载 Python 功能模块。

**Architecture:** Python 标准库 HTTP 服务提供页面和同源 API。独立的 Manager 负责持久化与依赖检查，Installer 负责 ZIP 校验和原子安装，Worker 以独立进程执行模块。

**Tech Stack:** Python 3.10+、HTML/CSS/JavaScript、unittest，无第三方运行依赖。

## 已确认设计

- ZIP 可以是模块文件直接位于根目录，或只有一层模块目录。必须包含 manifest.json 和 plugin.py。
- 安装只检查元数据，不执行模块。默认禁用，不自动安装 pip 依赖，不覆盖同名模块。
- manifest 包含 id、name、version、description、dependencies；dependencies 为模块 ID 列表，首版不解析版本约束。
- 插件统一导出 run(context)。context 提供 config、data_dir、log、should_stop 和 wait。
- 启用要求依赖已启用；运行要求依赖已运行；停止和移除会保护使用该模块的其他模块。
- 运行模块的配置和代码不能直接修改；停止后修改，下次运行生效。模块通过标准接口集成，不依赖管理页面修改。
- 网页只监听 127.0.0.1，写操作校验 Origin 和会话令牌。ZIP 有压缩体积、解压体积、数量限制，拒绝路径穿越和链接。
- 启用状态、配置持久化；服务重启后不自动运行插件。卸载保留数据和配置，移除代码到本机回收目录。

## 执行步骤

- [x] 1. tests/test_manager.py：写实际 ZIP 安装、恶意路径、重复安装、缺失/循环依赖、进程启停、配置重启保留的测试；运行 `python -m unittest discover -s tests -v` 确认功能尚未实现。
- [x] 2. core/manifest.py、installer.py、runtime.py、manager.py：实现元数据校验、临时解压和重命名、进程上下文、状态原子写入和依赖保护；运行上述测试直至通过。
- [x] 3. manager.py、web/index.html、web/app.js、web/style.css：实现同源 HTTP API 与中文管理界面，覆盖模块列表、搜索、ZIP 上传、启停、配置、日志、卸载确认。
- [x] 4. modules/heartbeat：添加可观察日志的示例；examples：提供可上传的独立 ZIP；start.bat：Windows 双击启动；README.md：说明模块接口与操作方式。
- [x] 5. HTTP 集成测试验证页面、状态、令牌、上传与配置。浏览器核验实际页面并运行完整测试。

当前目录没有 Git 仓库，不自动创建仓库或提交。
