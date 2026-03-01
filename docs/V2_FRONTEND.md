# V2 Frontend

前端目录：`frontend/`

## 技术栈
- React + TypeScript + Vite
- Ant Design
- TanStack Query
- Zustand

## 本地运行
```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`

API 基地址环境变量：
- `VITE_API_BASE_URL`（默认 `http://127.0.0.1:8001`）

## 页面
- `/` 论文探索
- `/recommendations` 推荐
- `/research` 深度调研
- `/reports` 日报
- `/tasks` 任务中心
- `/settings` 设置

## 注意
- 设置保存后立即生效（仅影响新任务）。
- 无 PDF 论文在列表中会显示“无PDF”标签。
