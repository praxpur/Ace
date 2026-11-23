# 分刷酱 · Ace

Ace（分刷酱）在一个桌面窗口提供超星学习通和智慧树课程任务。界面使用 Vue 3、Element Plus 和 PyWebView，配有浅色与深色主题、开发者信息和 Windows 系统托盘；两个平台的运行逻辑各自保留，账号与登录态不互通。

## 使用

源码运行需要 Windows、Python 3.13+、Node.js 和 Playwright Chromium。普通使用者可从 GitHub Releases 下载已打包的 Windows 便携版。

Windows 发布版：[Ace 0.2.0](https://github.com/praxpur/Ace/releases/latest)。首次运行时配置会在应用目录中新建；登录信息与 cookies 仅保存在本机，请勿分享个人配置文件。

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
cd frontend
npm ci
npm run build
cd ..
python gui_main.py
```

左侧顶部的平台切换器可在“超星学习通”与“智慧树”之间切换，两个平台共用统一的“账号与配置、课程与目录、运行面板”三级导航、Element Plus 表格与控制台终端。智慧树首次登录需要可见浏览器；选择课程后先扫描全部课程，随后勾选视频（支持“选未完成”），点击“开始刷课”才建立播放队列。已完成视频不会自动勾选。

超星与智慧树的界面配置统一保存在 `gui_config.json`，智慧树登录态默认保存在 `.state/auth.json`。这些文件被 Git 忽略，请勿分享。

左下角可选择“浅色模式、深色模式、跟随系统”，选择后自动保存，重启后恢复；默认跟随系统，并实时响应系统主题变化。

左下角的开发者卡片可打开“关于分刷酱”，查看开发者信息、GitHub、个人网站与开源来源。界面支持轻量过渡动效，并遵循系统的减少动态效果设置。

Windows 下关闭或最小化窗口会隐藏到系统托盘，后台任务继续运行。双击托盘图标可恢复主窗口，右键菜单可显示、隐藏或退出程序；选择退出时会停止任务并清理托盘图标。

## 构建 Windows 程序

先运行前端构建，然后设置 `PLAYWRIGHT_BROWSERS_PATH` 指向已安装的 Playwright 浏览器目录，再执行 `pyinstaller --noconfirm --clean Fenshuajiang.spec`。冻结程序打包 Chromium。当前仓库保留了源项目的测试与文档；两个平台的真实账号流程仍需在目标账号上验收。

## 来源和许可

超星部分基于本地 `chaoxing-gui` 项目，包含其上游 [Samueli924/chaoxing](https://github.com/Samueli924/chaoxing) 的代码，按本仓库 `LICENSE`（GPL-3.0）发布，原说明见 [docs/chaoxing-original-readme.md](docs/chaoxing-original-readme.md)。智慧树 `src/treehouse` 来自本地 Treehouse-Course 项目，原 MIT 许可见 `TREEHOUSE-LICENSE`。合并项目整体按 GPL-3.0 发布，并保留智慧树部分的 MIT 许可声明。
