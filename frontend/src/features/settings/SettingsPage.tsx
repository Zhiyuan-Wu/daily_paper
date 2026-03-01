import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Collapse,
  Col,
  Input,
  InputNumber,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
  message
} from "antd";

import { getSettings, getSourceAvailability, getSystemStatus, updateSettings } from "../../shared/api/client";

const { Title, Text } = Typography;

function parseList(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function toNum(v: unknown, fallback: number): number {
  const n = Number(v);
  if (Number.isNaN(n)) {
    return fallback;
  }
  return n;
}

export function SettingsPage() {
  const [msg, holder] = message.useMessage();
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings
  });
  const statusQuery = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus,
    refetchInterval: 15000
  });
  const sourceQuery = useQuery({
    queryKey: ["source-availability"],
    queryFn: () => getSourceAvailability(7),
    refetchInterval: 60000
  });

  const [dailySources, setDailySources] = useState("arxiv, huggingface");
  const [dailyKeywords, setDailyKeywords] = useState("");
  const [dailyArxivCategories, setDailyArxivCategories] = useState("cs.AI, cs.LG, cs.CL, cs.CV, cs.RO, stat.ML");
  const [dailyTopK, setDailyTopK] = useState(5);
  const [dailyWindowDays, setDailyWindowDays] = useState(7);

  const [weights, setWeights] = useState<Record<string, number>>({
    keyword_semantic: 0.2,
    interested_semantic: 0.2,
    repetition_penalty: 0.2,
    llm_theme: 0.2,
    recommended_inverse: 0.2
  });

  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [scholarRateLimit, setScholarRateLimit] = useState(2);
  const [downloadConcurrency, setDownloadConcurrency] = useState(4);
  const [parseConcurrency, setParseConcurrency] = useState(2);
  const [analyzeConcurrency, setAnalyzeConcurrency] = useState(2);
  const [pdfLruBytes, setPdfLruBytes] = useState(10 * 1024 * 1024 * 1024);
  const [pdfLruCount, setPdfLruCount] = useState(5000);
  const [ocrTimeout, setOcrTimeout] = useState(120);
  const [researchTimeout, setResearchTimeout] = useState(45);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }

    const settings = settingsQuery.data;
    setDailySources((settings.daily_report_sources as string[] | undefined)?.join(", ") || "arxiv, huggingface");
    setDailyKeywords((settings.daily_report_keywords as string[] | undefined)?.join(", ") || "");
    setDailyArxivCategories(
      (settings.daily_report_arxiv_categories as string[] | undefined)?.join(", ") || "cs.AI, cs.LG, cs.CL, cs.CV, cs.RO, stat.ML"
    );
    setDailyTopK(toNum(settings.daily_report_top_k, 5));
    setDailyWindowDays(toNum(settings.daily_report_window_days, 7));

    setWeights((settings.recommend_strategy_weights as Record<string, number>) || {});

    setTimezone(String(settings.timezone || "Asia/Shanghai"));
    setScholarRateLimit(toNum(settings.scholar_rate_limit_rps, 2));
    setDownloadConcurrency(toNum(settings.batch_download_concurrency, 4));
    setParseConcurrency(toNum(settings.batch_parse_concurrency, 2));
    setAnalyzeConcurrency(toNum(settings.batch_analyze_concurrency, 2));
    setPdfLruBytes(toNum(settings.pdf_lru_max_bytes, 10 * 1024 * 1024 * 1024));
    setPdfLruCount(toNum(settings.pdf_lru_max_count, 5000));
    setOcrTimeout(toNum(settings.ocr_timeout_seconds, 120));
    setResearchTimeout(toNum(settings.research_timeout_minutes, 45));
  }, [settingsQuery.data]);

  const saveMut = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateSettings(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      msg.success("设置已保存");
    },
    onError: (error) => msg.error(String(error))
  });

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {holder}
      <Title level={3} style={{ marginBottom: 0 }}>
        设置
      </Title>

      <Card title="系统状态" loading={statusQuery.isLoading}>
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <Statistic title="系统时间" value={statusQuery.data?.system_time || "-"} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic title="论文数量" value={statusQuery.data?.paper_count || 0} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic title="日报数量" value={statusQuery.data?.daily_report_count || 0} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic title="任务数量" value={statusQuery.data?.research_task_count || 0} />
          </Col>
        </Row>
        <Space size={8} wrap style={{ marginTop: 16 }}>
          {Object.entries(statusQuery.data?.service_health || {}).map(([name, ok]) => (
            <Tag key={name} color={ok ? "green" : "red"}>
              {name}: {ok ? "connected" : "disconnected"}
            </Tag>
          ))}
        </Space>
        <Space size={8} wrap style={{ marginTop: 8 }}>
          {Object.entries(sourceQuery.data?.sources || {}).map(([name, item]) => (
            <Tag key={name} color={item.ok ? "green" : "red"}>
              {name}: {item.ok ? `ok(${item.count})` : item.reason || "unavailable"}
            </Tag>
          ))}
        </Space>
      </Card>

      <Collapse
        defaultActiveKey={["daily", "recommend", "system"]}
        items={[
          {
            key: "daily",
            label: "日报选项配置",
            children: (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Text>数据源（逗号分隔）</Text>
                  <Input value={dailySources} onChange={(e) => setDailySources(e.target.value)} />
                </Space>
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Text>关键词（逗号分隔）</Text>
                  <Input value={dailyKeywords} onChange={(e) => setDailyKeywords(e.target.value)} />
                </Space>
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Text>arXiv 分区（逗号分隔）</Text>
                  <Input value={dailyArxivCategories} onChange={(e) => setDailyArxivCategories(e.target.value)} />
                </Space>
                <Space>
                  <Space direction="vertical">
                    <Text>时间窗口（天）</Text>
                    <InputNumber min={1} max={30} value={dailyWindowDays} onChange={(v) => setDailyWindowDays(toNum(v, 1))} />
                  </Space>
                  <Space direction="vertical">
                    <Text>日报 Top K</Text>
                    <InputNumber min={1} max={50} value={dailyTopK} onChange={(v) => setDailyTopK(toNum(v, 5))} />
                  </Space>
                </Space>
                <Button
                  type="primary"
                  loading={saveMut.isPending}
                  onClick={() =>
                    saveMut.mutate({
                      daily_report_sources: parseList(dailySources),
                      daily_report_keywords: parseList(dailyKeywords),
                      daily_report_arxiv_categories: parseList(dailyArxivCategories),
                      daily_report_window_days: dailyWindowDays,
                      daily_report_top_k: dailyTopK
                    })
                  }
                >
                  保存日报配置
                </Button>
              </Space>
            )
          },
          {
            key: "recommend",
            label: "推荐算法参数配置",
            children: (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {Object.keys(weights).map((key) => (
                  <Space key={key} align="center">
                    <Text style={{ width: 220 }}>{key}</Text>
                    <InputNumber
                      min={0}
                      max={1}
                      step={0.05}
                      value={weights[key]}
                      onChange={(v) =>
                        setWeights((prev) => ({
                          ...prev,
                          [key]: toNum(v, prev[key] || 0)
                        }))
                      }
                    />
                  </Space>
                ))}
                <Button
                  type="primary"
                  loading={saveMut.isPending}
                  onClick={() => saveMut.mutate({ recommend_strategy_weights: weights })}
                >
                  保存推荐参数
                </Button>
              </Space>
            )
          },
          {
            key: "system",
            label: "系统设置配置",
            children: (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space wrap>
                  <Space direction="vertical">
                    <Text>时区</Text>
                    <Input style={{ width: 200 }} value={timezone} onChange={(e) => setTimezone(e.target.value)} />
                  </Space>
                  <Space direction="vertical">
                    <Text>学术源限流 RPS</Text>
                    <InputNumber min={0.5} max={30} step={0.5} value={scholarRateLimit} onChange={(v) => setScholarRateLimit(toNum(v, 2))} />
                  </Space>
                </Space>
                <Space wrap>
                  <Space direction="vertical">
                    <Text>下载并发</Text>
                    <InputNumber min={1} value={downloadConcurrency} onChange={(v) => setDownloadConcurrency(toNum(v, 4))} />
                  </Space>
                  <Space direction="vertical">
                    <Text>解析并发</Text>
                    <InputNumber min={1} value={parseConcurrency} onChange={(v) => setParseConcurrency(toNum(v, 2))} />
                  </Space>
                  <Space direction="vertical">
                    <Text>分析并发</Text>
                    <InputNumber min={1} value={analyzeConcurrency} onChange={(v) => setAnalyzeConcurrency(toNum(v, 2))} />
                  </Space>
                </Space>
                <Space wrap>
                  <Space direction="vertical">
                    <Text>PDF LRU 最大字节</Text>
                    <InputNumber min={1} value={pdfLruBytes} onChange={(v) => setPdfLruBytes(toNum(v, 10 * 1024 * 1024 * 1024))} />
                  </Space>
                  <Space direction="vertical">
                    <Text>PDF LRU 最大数量</Text>
                    <InputNumber min={1} value={pdfLruCount} onChange={(v) => setPdfLruCount(toNum(v, 5000))} />
                  </Space>
                </Space>
                <Space wrap>
                  <Space direction="vertical">
                    <Text>OCR 超时（秒）</Text>
                    <InputNumber min={1} value={ocrTimeout} onChange={(v) => setOcrTimeout(toNum(v, 120))} />
                  </Space>
                  <Space direction="vertical">
                    <Text>调研超时（分钟）</Text>
                    <InputNumber min={1} value={researchTimeout} onChange={(v) => setResearchTimeout(toNum(v, 45))} />
                  </Space>
                </Space>
                <Button
                  type="primary"
                  loading={saveMut.isPending}
                  onClick={() =>
                    saveMut.mutate({
                      timezone,
                      scholar_rate_limit_rps: scholarRateLimit,
                      batch_download_concurrency: downloadConcurrency,
                      batch_parse_concurrency: parseConcurrency,
                      batch_analyze_concurrency: analyzeConcurrency,
                      pdf_lru_max_bytes: pdfLruBytes,
                      pdf_lru_max_count: pdfLruCount,
                      ocr_timeout_seconds: ocrTimeout,
                      research_timeout_minutes: researchTimeout
                    })
                  }
                >
                  保存系统配置
                </Button>
              </Space>
            )
          }
        ]}
      />
    </Space>
  );
}
