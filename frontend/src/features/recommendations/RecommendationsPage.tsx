import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Input, Space, Table, Typography } from "antd";

import { generateRecommendations } from "../../shared/api/client";

const { Title } = Typography;

export function RecommendationsPage() {
  const [paperUidsText, setPaperUidsText] = useState("");
  const [rows, setRows] = useState<any[]>([]);

  const mut = useMutation({
    mutationFn: () =>
      generateRecommendations({
        paper_uids: paperUidsText
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        top_k: 10
      }),
    onSuccess: (data) => setRows(data.result?.items || [])
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Title level={3}>推荐结果</Title>
      <Card>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            placeholder="输入 paper_uid，逗号分隔"
            value={paperUidsText}
            onChange={(e) => setPaperUidsText(e.target.value)}
          />
          <Button type="primary" loading={mut.isPending} onClick={() => mut.mutate()}>
            生成推荐
          </Button>
        </Space.Compact>
      </Card>

      <Table
        rowKey="paper_uid"
        dataSource={rows}
        columns={[
          { title: "Paper UID", dataIndex: "paper_uid" },
          { title: "分数", dataIndex: "score" },
          { title: "排名", dataIndex: "rank" },
          {
            title: "理由",
            dataIndex: "reasons",
            render: (reasons: string[]) => (reasons || []).join("; ")
          }
        ]}
      />
    </Space>
  );
}
