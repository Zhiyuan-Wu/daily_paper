import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Input, Space, Typography } from "antd";

import { createResearchTask, getResearchResult } from "../../shared/api/client";

const { Title, Paragraph } = Typography;

export function ResearchPage() {
  const [topic, setTopic] = useState("多模态 Agent 在科学发现中的应用");
  const [taskId, setTaskId] = useState("");
  const [report, setReport] = useState("");

  const createMut = useMutation({
    mutationFn: () => createResearchTask({ topic, constraints: { lang: "zh" } }),
    onSuccess: (data) => {
      const tid = data.result?.task_id || data.task_id;
      setTaskId(tid);
    }
  });

  const resultMut = useMutation({
    mutationFn: () => getResearchResult(taskId),
    onSuccess: (data) => setReport(data.report_md || "")
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Title level={3}>深度调研</Title>
      <Card>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input.TextArea value={topic} onChange={(e) => setTopic(e.target.value)} rows={3} />
          <Button type="primary" loading={createMut.isPending} onClick={() => createMut.mutate()}>
            创建调研任务
          </Button>
          {taskId ? (
            <Space>
              <span>任务ID: {taskId}</span>
              <Button onClick={() => resultMut.mutate()} loading={resultMut.isPending}>
                拉取结果
              </Button>
            </Space>
          ) : null}
        </Space>
      </Card>
      <Card>
        <Paragraph style={{ whiteSpace: "pre-wrap" }}>{report || "暂无报告"}</Paragraph>
      </Card>
    </Space>
  );
}
