import { Layout, Menu } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const { Header, Content } = Layout;

export function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ display: "flex", alignItems: "center" }}>
        <div style={{ color: "#fff", marginRight: 24, fontWeight: 700 }}>Daily Paper V2</div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[loc.pathname]}
          onClick={(e) => nav(e.key)}
          items={[
            { key: "/", label: "论文探索" },
            { key: "/recommendations", label: "推荐" },
            { key: "/research", label: "调研" },
            { key: "/reports", label: "日报" },
            { key: "/tasks", label: "任务" },
            { key: "/settings", label: "设置" }
          ]}
        />
      </Header>
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
