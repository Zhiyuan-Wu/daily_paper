import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PlusOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, Input, List, Row, Space, Tag, Typography, message } from "antd";
import axios from "axios";

import { createResearchTask, getResearchResult, listResearchTasks } from "../../shared/api/client";

const { Title, Paragraph, Text } = Typography;

export function ResearchPage() {
  const [topic, setTopic] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [report, setReport] = useState("");
  const [msg, holder] = message.useMessage();

  const tasksQuery = useQuery({
    queryKey: ["research-tasks"],
    queryFn: () => listResearchTasks(100)
  });

  const selectedTask = useMemo(
    () => tasksQuery.data?.items.find((item) => item.task_id === selectedTaskId) || null,
    [selectedTaskId, tasksQuery.data?.items]
  );

  const createMut = useMutation({
    mutationFn: () => createResearchTask({ topic: topic.trim(), constraints: { lang: "zh", depth: "deep" } }),
    onSuccess: async (data) => {
      const taskId = data.result?.task_id || data.task_id;
      await tasksQuery.refetch();
      setSelectedTaskId(taskId);
      setTopic("");
      resultMut.mutate(taskId);
    },
    onError: (error) => msg.error(String(error))
  });

  const resultMut = useMutation({
    mutationFn: (taskId: string) => getResearchResult(taskId),
    onSuccess: (data) => setReport(data.report_md || ""),
    onError: (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setReport("");
        return;
      }
      msg.error(String(error));
    }
  });

  const showCreateView = !selectedTaskId;

  return (
    <Row gutter={16} style={{ minHeight: "calc(100vh - 130px)" }}>
      {holder}
      <Col xs={24} lg={16} style={{ display: "flex" }}>
        <Card style={{ width: "100%", borderRadius: 12 }}>
          {showCreateView ? (
            <Space direction="vertical" size={24} style={{ width: "100%", paddingTop: 80, alignItems: "center" }}>
              <Title level={3} style={{ marginBottom: 0 }}>
                新建深度调研任务
              </Title>
              <Space.Compact style={{ width: "min(800px, 100%)" }}>
                <Input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="输入调研主题，例如：多模态 Agent 在科研自动化中的应用"
                  size="large"
                />
                <Button
                  type="primary"
                  size="large"
                  loading={createMut.isPending}
                  disabled={!topic.trim()}
                  onClick={() => createMut.mutate()}
                >
                  创建调研
                </Button>
              </Space.Compact>
            </Space>
          ) : (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Title level={4} style={{ marginBottom: 0 }}>
                {selectedTask?.topic || "调研报告"}
              </Title>
              <Text type="secondary">
                任务状态：{selectedTask?.status || "-"} / 开始时间：{selectedTask?.started_at || "-"}
              </Text>
              <Button
                onClick={() => selectedTaskId && resultMut.mutate(selectedTaskId)}
                loading={resultMut.isPending}
                style={{ width: "fit-content" }}
              >
                刷新报告
              </Button>
              <Card size="small">
                <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                  {report || "任务还在运行，或该任务暂无可展示报告。"}
                </Paragraph>
              </Card>
            </Space>
          )}
        </Card>
      </Col>

      <Col xs={24} lg={8} style={{ display: "flex" }}>
        <Card
          title="历史调研任务"
          extra={
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setSelectedTaskId(null);
                setReport("");
              }}
            >
              新的调研
            </Button>
          }
          style={{ width: "100%", borderRadius: 12 }}
          bodyStyle={{ paddingTop: 8 }}
        >
          {tasksQuery.data?.items.length ? (
            <List
              dataSource={tasksQuery.data?.items || []}
              renderItem={(item) => (
                <List.Item style={{ paddingInline: 0 }}>
                  <Card
                    size="small"
                    hoverable
                    style={{
                      width: "100%",
                      borderColor: selectedTaskId === item.task_id ? "#1677ff" : undefined
                    }}
                    onClick={() => {
                      setSelectedTaskId(item.task_id);
                      resultMut.mutate(item.task_id);
                    }}
                  >
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      <Text strong ellipsis>
                        {item.topic || "未命名主题"}
                      </Text>
                      <Space size={8} wrap>
                        <Tag color={item.status === "completed" ? "green" : item.status === "failed" ? "red" : "blue"}>
                          {item.status}
                        </Tag>
                        <Text type="secondary">{item.started_at || item.finished_at || "-"}</Text>
                      </Space>
                    </Space>
                  </Card>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无历史任务" />
          )}
        </Card>
      </Col>
    </Row>
  );
}
