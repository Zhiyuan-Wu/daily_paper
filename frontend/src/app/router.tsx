import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./App";
import { PapersPage } from "../features/papers/PapersPage";
import { RecommendationsPage } from "../features/recommendations/RecommendationsPage";
import { ResearchPage } from "../features/research/ResearchPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { TasksPage } from "../features/tasks/TasksPage";
import { SettingsPage } from "../features/settings/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <PapersPage /> },
      { path: "recommendations", element: <RecommendationsPage /> },
      { path: "research", element: <ResearchPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "tasks", element: <TasksPage /> },
      { path: "settings", element: <SettingsPage /> }
    ]
  }
]);
