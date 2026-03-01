import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./App";
import { PapersPage } from "../features/papers/PapersPage";
import { ResearchPage } from "../features/research/ResearchPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { SettingsPage } from "../features/settings/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/reports" replace /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "papers", element: <PapersPage /> },
      { path: "research", element: <ResearchPage /> },
      { path: "settings", element: <SettingsPage /> }
    ]
  }
]);
