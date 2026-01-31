# Eval-vault 🛡️

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![WebView](https://img.shields.io/badge/Engine-PyWebView-orange?logo=microsoftedge&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)

**Eval-vault** 是一款基于 Python 开发的轻量级、高性能多媒体安全加密库与播放器。采用流式解密技术，专为保护个人隐私视频与图片而设计。

---

## ✨ 核心特性

- **🚀 高效流式处理**：采用多线程 HTTP 服务后端，解密播放无需等待，支持视频进度条随意拖拽。
- **🔒 混合加密方案**：基于位异或（XOR）算法对媒体文件进行深度混淆，后缀名为专属的 `.bmm`。
- **📁 智能文件夹管理**：支持拖拽整个文件夹，自动识别内部媒体文件并保持原目录结构生成加密镜像。
- **🛡️ 身份验证**：内置硬编码启动口令验证，防止未授权访问。
- **🎨 现代播放界面**：侧边栏列表悬停显示，支持视频倍速调节（`[` 和 `]` 键）。

---

## 🛠️ 技术栈

- **GUI 框架**: `Tkinter` + `TkinterDnD2` (提供拖拽支持)
- **Web 内核**: `PyWebView` (用于高性能视频渲染与 CSS 布局)
- **后端服务**: `Python ThreadedHTTPServer` (实现多线程流式数据传输)
- **数据处理**: `Byte Translation` (高效 XOR 位运算加密)

---

## 🚀 快速开始

### 1. 环境准备
确保你的环境中已安装必要的依赖库：
```bash
pip install pywebview tkinterdnd2