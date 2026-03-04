import { Suspense, lazy, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./App";

const ReportsPage = lazy(() => import("../features/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const PapersPage = lazy(() => import("../features/papers/PapersPage").then((m) => ({ default: m.PapersPage })));
const ResearchPage = lazy(() => import("../features/research/ResearchPage").then((m) => ({ default: m.ResearchPage })));
const SettingsPage = lazy(() => import("../features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const RecommendationsPage = lazy(() =>
  import("../features/recommendations/RecommendationsPage").then((m) => ({ default: m.RecommendationsPage }))
);
const TasksPage = lazy(() => import("../features/tasks/TasksPage").then((m) => ({ default: m.TasksPage })));

function withPageSuspense(page: ReactNode) {
  return <Suspense fallback={<div style={{ padding: 16 }}>加载中...</div>}>{page}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/reports" replace /> },
      { path: "reports", element: withPageSuspense(<ReportsPage />) },
      { path: "papers", element: withPageSuspense(<PapersPage />) },
      { path: "research", element: withPageSuspense(<ResearchPage />) },
      { path: "settings", element: withPageSuspense(<SettingsPage />) },
      { path: "recommendations", element: withPageSuspense(<RecommendationsPage />) },
      { path: "tasks", element: withPageSuspense(<TasksPage />) },
    ]
  }
]);
