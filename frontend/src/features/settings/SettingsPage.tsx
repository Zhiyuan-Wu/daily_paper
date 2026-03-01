import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, InputNumber, Space, Typography } from "antd";

import { getSettings, updateSettings } from "../../shared/api/client";

const { Title } = Typography;

export function SettingsPage() {
  const [ocrTimeout, setOcrTimeout] = useState<number>(120);
  const [researchTimeout, setResearchTimeout] = useState<number>(45);

  useEffect(() => {
    getSettings().then((data) => {
      setOcrTimeout(Number(data.ocr_timeout_seconds || 120));
      setResearchTimeout(Number(data.research_timeout_minutes || 45));
    });
  }, []);

  const mut = useMutation({
    mutationFn: () =>
      updateSettings({
        ocr_timeout_seconds: ocrTimeout,
        research_timeout_minutes: researchTimeout
      })
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Title level={3}>设置（保存后立即生效）</Title>
      <Card>
        <Space direction="vertical">
          <Space>
            <span>OCR 超时（秒）</span>
            <InputNumber min={1} value={ocrTimeout} onChange={(v) => setOcrTimeout(Number(v || 120))} />
          </Space>
          <Space>
            <span>调研超时（分钟）</span>
            <InputNumber min={1} value={researchTimeout} onChange={(v) => setResearchTimeout(Number(v || 45))} />
          </Space>
          <Button type="primary" onClick={() => mut.mutate()} loading={mut.isPending}>
            保存
          </Button>
        </Space>
      </Card>
    </Space>
  );
}
