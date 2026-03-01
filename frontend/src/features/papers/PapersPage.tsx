import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Col, Input, Row, Space, Table, Typography, message } from "antd";

import { PdfAvailabilityTag } from "../../shared/components/PdfAvailabilityTag";
import { importPaper, searchPapers, type SearchItem } from "../../shared/api/client";

const { Title } = Typography;

export function PapersPage() {
  const [keywordsText, setKeywordsText] = useState("agent");
  const [rows, setRows] = useState<SearchItem[]>([]);
  const [msg, ctx] = message.useMessage();

  const searchMut = useMutation({
    mutationFn: () =>
      searchPapers({
        sources: ["openalex"],
        keywords: keywordsText
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        page: 1,
        page_size: 20
      }),
    onSuccess: (data) => setRows(data.items || []),
    onError: (err: unknown) => msg.error(String(err))
  });

  const importMut = useMutation({
    mutationFn: (row: SearchItem) =>
      importPaper({
        source: row.source,
        external_id: row.external_id,
        pdf_url: row.pdf_url
      }),
    onSuccess: () => msg.success("导入完成"),
    onError: (err: unknown) => msg.error(String(err))
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      {ctx}
      <Title level={3}>论文探索</Title>
      <Card>
        <Row gutter={12}>
          <Col flex="auto">
            <Input
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="关键词，逗号分隔"
            />
          </Col>
          <Col>
            <Button type="primary" loading={searchMut.isPending} onClick={() => searchMut.mutate()}>
              搜索
            </Button>
          </Col>
        </Row>
      </Card>

      <Table
        rowKey="paper_uid"
        dataSource={rows}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "标题", dataIndex: "title", width: "45%" },
          {
            title: "来源",
            dataIndex: "source",
            render: (_, row) => (
              <Space>
                <span>{row.source}</span>
                <PdfAvailabilityTag unavailable={row.pdf_unavailable} />
              </Space>
            )
          },
          {
            title: "作者",
            dataIndex: "authors",
            render: (authors: string[]) => authors?.slice(0, 2).join(", ") || "-"
          },
          {
            title: "操作",
            render: (_, row) => (
              <Button
                onClick={() => importMut.mutate(row)}
                disabled={row.pdf_unavailable}
                loading={importMut.isPending}
              >
                导入
              </Button>
            )
          }
        ]}
      />
    </Space>
  );
}
