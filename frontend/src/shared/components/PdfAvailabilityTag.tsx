import { Tag } from "antd";

export function PdfAvailabilityTag({ unavailable }: { unavailable: boolean }) {
  if (!unavailable) {
    return <Tag color="green">PDF可用</Tag>;
  }
  return <Tag color="orange">无PDF</Tag>;
}
