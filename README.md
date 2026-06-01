# Hand Gesture Control System

基于 MediaPipe 的手势识别控制系统，支持实时手势识别、虚拟鼠标控制和 Web 交互界面。

## 功能特性

- 实时手部关键点检测 (MediaPipe Hands)
- 手势匹配与识别
- 虚拟鼠标控制 (手势模拟鼠标操作)
- Web 可视化界面 (Next.js)
- WebSocket 实时通信
- RESTful API 接口

## 技术栈

- **手势识别**: MediaPipe, OpenCV
- **后端**: FastAPI (Python), WebSocket
- **前端**: Next.js (React), TypeScript, Tailwind CSS
- **鼠标控制**: PyAutoGUI
- **UI组件**: Radix UI, Framer Motion

## 快速启动

### 后端

```bash
pip install -r requirements.txt
python backend/main.py
```

### 前端

```bash
cd web
npm install
npm run dev
```

## 访问地址

- 前端界面: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs
