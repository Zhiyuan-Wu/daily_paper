import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, DatePicker, Input, Space, Typography } from "antd";
import dayjs from "dayjs";

import { generateDailyReport, getDailyReport } from "../../shared/api/client";

const { Title, Paragraph } = Typography;

export function ReportsPage() {
  const [reportDate, setReportDate] = useState(dayjs());
  const [keywordsText, setKeywordsText] = useState("agent");
  const [reportId, setReportId] = useState("");
  const [reportMd, setReportMd] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      generateDailyReport({
        report_date: reportDate.format("YYYY-MM-DD"),
        sources: ["openalex"],
        keywords: keywordsText
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        top_k: 5
      }),
    onSuccess: (data) => setReportId(data.result?.report_id || "")
  });

  const getMut = useMutation({
    mutationFn: () => getDailyReport(reportId),
    onSuccess: (data) => setReportMd(data.summary_md || "")
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Title level={3}>日报</Title>
      <Card>
        <Space>
          <DatePicker value={reportDate} onChange={(d) => d && setReportDate(d)} />
          <Input
            style={{ width: 320 }}
            value={keywordsText}
            onChange={(e) => setKeywordsText(e.target.value)}
            placeholder="关键词"
          />
          <Button type="primary" loading={createMut.isPending} onClick={() => createMut.mutate()}>
            生成日报
          </Button>
          <Button disabled={!reportId} loading={getMut.isPending} onClick={() => getMut.mutate()}>
            拉取日报
          </Button>
        </Space>
      </Card>
      <Card>
        <Paragraph style={{ whiteSpace: "pre-wrap" }}>{reportMd || "暂无日报内容"}</Paragraph>
      </Card>
    </Space>
  );
}
