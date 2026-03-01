import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Input, Space, Typography } from "antd";

import { getTask } from "../../shared/api/client";

const { Title, Paragraph } = Typography;

export function TasksPage() {
  const [jobId, setJobId] = useState("");
  const [payload, setPayload] = useState<any>(null);

  const mut = useMutation({
    mutationFn: () => getTask(jobId),
    onSuccess: (data) => setPayload(data)
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Title level={3}>任务中心</Title>
      <Card>
        <Space.Compact style={{ width: "100%" }}>
          <Input value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="输入 job_id" />
          <Button type="primary" onClick={() => mut.mutate()} loading={mut.isPending}>
            查询
          </Button>
        </Space.Compact>
      </Card>
      <Card>
        <Paragraph style={{ whiteSpace: "pre-wrap" }}>
          {payload ? JSON.stringify(payload, null, 2) : "暂无结果"}
        </Paragraph>
      </Card>
    </Space>
  );
}
