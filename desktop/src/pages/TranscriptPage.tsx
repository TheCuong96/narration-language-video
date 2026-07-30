import { useMemo, useState } from "react";
import type { SegmentRow } from "../lib/types";

interface Props {
  stem: string | null;
  segments: SegmentRow[];
  onChange: (segments: SegmentRow[]) => void;
  onSaveContinue: () => void;
  busy: boolean;
}

export function TranscriptPage({
  stem,
  segments,
  onChange,
  onSaveContinue,
  busy,
}: Props) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return segments.map((s, i) => ({ s, i }));
    return segments
      .map((s, i) => ({ s, i }))
      .filter(
        ({ s }) =>
          s.text_en.toLowerCase().includes(needle) ||
          s.text_vi.toLowerCase().includes(needle),
      );
  }, [segments, q]);

  if (!stem) {
    return (
      <section className="panel">
        <h2>Transcript editor</h2>
        <p className="muted">
          Chưa có bản dịch để sửa. Bật «Sửa bản dịch trước TTS» rồi chạy job, hoặc mở
          mục đang ở trạng thái Review trong hàng đợi.
        </p>
      </section>
    );
  }

  return (
    <section className="panel review">
      <h2>Transcript — {stem}</h2>
      <div className="row">
        <label>Tìm kiếm</label>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Lọc EN hoặc VI…"
        />
      </div>
      <div className="seg-head">
        <span>Thời gian</span>
        <span>Tiếng Anh</span>
        <span>Tiếng Việt (sửa được)</span>
      </div>
      {filtered.map(({ s, i }) => (
        <div className="seg" key={s.id}>
          <time>
            {s.start.toFixed(1)}–{s.end.toFixed(1)}s
          </time>
          <div className="en">{s.text_en}</div>
          <textarea
            value={s.text_vi}
            onChange={(e) => {
              const next = [...segments];
              next[i] = { ...s, text_vi: e.target.value };
              onChange(next);
            }}
          />
        </div>
      ))}
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={busy || !segments.length}
          onClick={onSaveContinue}
        >
          Lưu &amp; tiếp tục tạo giọng
        </button>
      </div>
    </section>
  );
}
