import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  EyeOutlined,
  FilePdfOutlined,
  HeartFilled,
  HeartOutlined,
  ReloadOutlined
} from "@ant-design/icons";
import { Button, Card, Modal, Space, Table, Tag, Typography, message } from "antd";

import { getPaperDetail, listPapers, sendPaperInteraction, type PaperDetail } from "../../shared/api/client";

const { Title, Paragraph, Text } = Typography;

export function PapersPage() {
  const [msg, holder] = message.useMessage();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const queryClient = useQueryClient();

  const papersQuery = useQuery({
    queryKey: ["papers", page, pageSize],
    queryFn: () => listPapers({ page, page_size: pageSize })
  });

  const detailMut = useMutation({
    mutationFn: (paperUid: string) => getPaperDetail(paperUid),
    onSuccess: (data) => {
      setDetail(data);
      setDetailOpen(true);
    },
    onError: (error) => msg.error(String(error))
  });

  const likeMut = useMutation({
    mutationFn: (paperUid: string) => sendPaperInteraction({ paper_uid: paperUid, action: "like" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["papers"] });
      await queryClient.invalidateQueries({ queryKey: ["system-status"] });
      msg.success("已标记为喜欢");
    },
    onError: (error) => msg.error(String(error))
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      {holder}
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Title level={3} style={{ marginBottom: 0 }}>
          论文探索
        </Title>
        <Button icon={<ReloadOutlined />} onClick={() => papersQuery.refetch()} loading={papersQuery.isFetching}>
          刷新
        </Button>
      </Space>

      <Card>
        <Table
          rowKey="paper_uid"
          loading={papersQuery.isLoading}
          dataSource={papersQuery.data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: papersQuery.data?.total || 0,
            onChange: (nextPage, nextSize) => {
              setPage(nextPage);
              setPageSize(nextSize);
            },
            showSizeChanger: true
          }}
          columns={[
            {
              title: "操作",
              width: 220,
              fixed: "left",
              render: (_, row) => (
                <Space size={4} wrap>
                  <Space size={2}>
                    <Button
                      type="text"
                      icon={<EyeOutlined />}
                      onClick={() => detailMut.mutate(row.paper_uid)}
                      title="查看详情"
                    />
                    <Button
                      type="text"
                      icon={<FilePdfOutlined />}
                      onClick={() => window.open(row.pdf_url || `/api/v1/papers/${row.paper_uid}/pdf`, "_blank", "noopener")}
                      title={row.has_pdf ? "阅读全文（本地PDF）" : "阅读全文（需要下载）"}
                    />
                    <Button
                      type="text"
                      icon={row.liked ? <HeartFilled style={{ color: "#f5222d" }} /> : <HeartOutlined />}
                      onClick={() => likeMut.mutate(row.paper_uid)}
                      loading={likeMut.isPending}
                      title="喜欢"
                    />
                  </Space>
                  <Tag color={row.has_pdf ? "green" : row.pdf_unavailable ? "red" : "gold"}>
                    {row.has_pdf ? "本地PDF" : row.pdf_unavailable ? "PDF可能不可用" : "需下载"}
                  </Tag>
                </Space>
              )
            },
            {
              title: "标题",
              dataIndex: "title",
              width: "55%",
              render: (title: string, row) => (
                <Space direction="vertical" size={2}>
                  <Text>{title}</Text>
                  <Text type="secondary">
                    {row.source} / {row.external_id}
                  </Text>
                </Space>
              )
            },
            {
              title: "时间",
              dataIndex: "published_at",
              width: 180,
              render: (value: string | null | undefined) => value || "-"
            },
            {
              title: "关键词",
              dataIndex: "keywords",
              render: (keywords: string[]) =>
                keywords?.length ? (
                  <Space size={[0, 8]} wrap>
                    {keywords.map((keyword) => (
                      <Tag key={keyword}>{keyword}</Tag>
                    ))}
                  </Space>
                ) : (
                  "-"
                )
            }
          ]}
        />
      </Card>

      <Modal
        width={900}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        title={detail?.title || "论文详情"}
      >
        {detail ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>发布时间：</Text>
              {detail.published_at || "-"}
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>作者：</Text>
              {detail.authors?.length ? detail.authors.join(", ") : "-"}
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>摘要：</Text>
              {detail.abstract || "-"}
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>分析结果：</Text>
            </Paragraph>
            <Card size="small">
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {detail.analysis ? JSON.stringify(detail.analysis, null, 2) : "暂无分析结果"}
              </pre>
            </Card>
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
}
