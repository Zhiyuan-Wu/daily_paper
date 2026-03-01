import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, DatePicker, Space, Tag, Typography, message } from "antd";
import axios from "axios";
import dayjs, { Dayjs } from "dayjs";

import { generateDailyReportAsync, getDailyReportByDate, getSettings, getTask } from "../../shared/api/client";

const { Title, Paragraph, Text } = Typography;

function toStringArray(raw: unknown, fallback: string[] = []): string[] {
  if (!Array.isArray(raw)) {
    return fallback;
  }
  return raw.map((x) => String(x).trim()).filter(Boolean);
}

function toInt(raw: unknown, fallback: number): number {
  const v = Number(raw);
  if (Number.isNaN(v)) {
    return fallback;
  }
  return v;
}

export function ReportsPage() {
  const [reportDate, setReportDate] = useState<Dayjs>(dayjs());
  const [activeJobId, setActiveJobId] = useState<string>("");
  const [jobStatus, setJobStatus] = useState<string>("");
  const [msg, holder] = message.useMessage();
  const queryClient = useQueryClient();
  const reportDateText = reportDate.format("YYYY-MM-DD");
  const isToday = reportDate.isSame(dayjs(), "day");

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings
  });

  const reportQuery = useQuery({
    queryKey: ["daily-report", reportDateText],
    queryFn: async () => {
      try {
        return await getDailyReportByDate(reportDateText);
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return null;
        }
        throw error;
      }
    }
  });

  const generateMut = useMutation({
    mutationFn: () => {
      const settings = settingsQuery.data || {};
      return generateDailyReportAsync({
        report_date: dayjs().format("YYYY-MM-DD"),
        sources: toStringArray(settings.daily_report_sources, ["arxiv", "huggingface"]),
        keywords: toStringArray(settings.daily_report_keywords, []),
        arxiv_categories: toStringArray(
          settings.daily_report_arxiv_categories,
          ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "stat.ML"]
        ),
        window_days: Math.max(1, toInt(settings.daily_report_window_days, 7)),
        top_k: Math.max(1, toInt(settings.daily_report_top_k, 5))
      });
    },
    onSuccess: (data) => {
      setActiveJobId(data.job_id);
      setJobStatus(data.status || "pending");
      msg.info("日报任务已提交，正在后台生成");
    },
    onError: (error) => msg.error(String(error))
  });

  const pollJobMut = useMutation({
    mutationFn: (jobId: string) => getTask(jobId),
    onSuccess: async (payload) => {
      setJobStatus(payload.status);
      if (payload.status === "completed") {
        setActiveJobId("");
        await queryClient.invalidateQueries({ queryKey: ["daily-report", dayjs().format("YYYY-MM-DD")] });
        await queryClient.invalidateQueries({ queryKey: ["system-status"] });
        setReportDate(dayjs());
        msg.success("今日日报已生成");
      } else if (payload.status === "failed") {
        setActiveJobId("");
        msg.error(payload.error_message || "日报生成失败");
      }
    },
    onError: (error) => {
      setActiveJobId("");
      msg.error(String(error));
    }
  });

  useEffect(() => {
    if (!activeJobId || pollJobMut.isPending) {
      return;
    }
    const timer = window.setTimeout(() => {
      pollJobMut.mutate(activeJobId);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [activeJobId, pollJobMut.isPending, pollJobMut.mutate]);

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {holder}
      <Title level={3} style={{ marginBottom: 0 }}>
        论文日报
      </Title>
      <Card>
        <Space size={12} wrap>
          <Text type="secondary">选择日期查看日报</Text>
          <DatePicker value={reportDate} onChange={(d) => d && setReportDate(d)} />
          {reportQuery.data ? <Tag color="green">已生成</Tag> : <Tag>暂无日报</Tag>}
          {activeJobId ? <Tag color="blue">任务中：{jobStatus || "pending"}</Tag> : null}
          {reportQuery.data?.created_at ? <Text type="secondary">生成时间：{reportQuery.data.created_at}</Text> : null}
        </Space>
      </Card>

      {!reportQuery.isLoading && !reportQuery.data ? (
        <Card>
          <Space direction="vertical" size={12}>
            <Paragraph style={{ marginBottom: 0 }}>
              {isToday ? "今天还没有日报。" : `${reportDateText} 还没有日报。`}
            </Paragraph>
            {isToday ? (
              <Button type="primary" loading={generateMut.isPending} onClick={() => generateMut.mutate()}>
                生成今日日报
              </Button>
            ) : null}
          </Space>
        </Card>
      ) : null}

      <Card loading={reportQuery.isLoading}>
        <Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
          {reportQuery.data?.summary_md || "请选择日期查看日报内容。"}
        </Paragraph>
      </Card>
    </Space>
  );
}
