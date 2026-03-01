import type { ReactNode } from "react";
import { BookOutlined, FileSearchOutlined, SearchOutlined, SettingOutlined } from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

export function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const selectedKey = loc.pathname === "/" ? "/reports" : loc.pathname;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={56} width={220} theme="light">
        <div style={{ padding: "20px 16px 12px" }}>
          <Title level={4} style={{ margin: 0 }}>
            Daily Paper
          </Title>
          <Text type="secondary">论文助手</Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          onClick={(e) => nav(e.key)}
          items={[
            { key: "/reports", label: "日报" },
            { key: "/papers", label: "论文探索" },
            { key: "/research", label: "深度调研" },
            { key: "/settings", label: "设置" }
          ].map((item) => {
            const iconMap: Record<string, ReactNode> = {
              "/reports": <BookOutlined />,
              "/papers": <FileSearchOutlined />,
              "/research": <SearchOutlined />,
              "/settings": <SettingOutlined />
            };
            return { ...item, icon: iconMap[item.key] };
          })}
        />
      </Sider>
      <Layout>
        <Content style={{ padding: 20 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
