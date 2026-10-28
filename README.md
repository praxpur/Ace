# 分刷酱

一个桌面窗口提供超星学习通和智慧树课程任务。界面沿用超星客户端的 Vue 3、Element Plus 和 PyWebView 设计；两个平台的运行逻辑各自保留，账号与登录态不互通。

## 使用

需要 Windows、Python 3.13+、Node.js 和 Playwright Chromium。

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
cd frontend
npm ci
npm run build
cd ..
python gui_main.py
```

左侧前三页是超星账号配置、课程列表和运行面板；“智慧树课程”页包含连接设置、课程与视频清单、运行监控。智慧树首次登录需要可见浏览器；选择课程后先扫描全部课程，随后手动勾选视频，点击“开始播放所选视频”才建立播放队列。已完成视频不会自动勾选。

超星配置保存在 `gui_config.json`，智慧树登录态默认保存在 `.state/auth.json`。这些文件被 Git 忽略，请勿分享。

## 构建 Windows 程序

先运行前端构建，然后设置 `PLAYWRIGHT_BROWSERS_PATH` 指向已安装的 Playwright 浏览器目录，再执行 `pyinstaller --noconfirm --clean Fenshuajiang.spec`。冻结程序打包 Chromium。当前仓库保留了源项目的测试与文档；两个平台的真实账号流程仍需在目标账号上验收。

## 来源和许可

超星部分基于本地 `chaoxing-gui` 项目，包含其上游 [Samueli924/chaoxing](https://github.com/Samueli924/chaoxing) 的代码，按本仓库 `LICENSE`（GPL-3.0）发布，原说明见 [docs/chaoxing-original-readme.md](docs/chaoxing-original-readme.md)。智慧树 `src/treehouse` 来自本地 Treehouse-Course 项目，原 MIT 许可见 `TREEHOUSE-LICENSE`。合并项目整体按 GPL-3.0 发布，并保留智慧树部分的 MIT 许可声明。
