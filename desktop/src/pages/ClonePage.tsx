import type { QueueItem } from "../lib/types";

interface Props {
  cloneSource: string;
  cloneStart: string;
  cloneEnd: string;
  cloneName: string;
  cloningSegment: boolean;
  busy: boolean;
  downloadingUrl: boolean;
  queue: QueueItem[];
  onCloneSource: (v: string) => void;
  onCloneStart: (v: string) => void;
  onCloneEnd: (v: string) => void;
  onCloneName: (v: string) => void;
  onCloneSegment: () => void;
  onPickCloneFile: () => void;
  onGoDub: () => void;
}

export function ClonePage(props: Props) {
  const {
    cloneSource,
    cloneStart,
    cloneEnd,
    cloneName,
    cloningSegment,
    busy,
    downloadingUrl,
    queue,
    onCloneSource,
    onCloneStart,
    onCloneEnd,
    onCloneName,
    onCloneSegment,
    onPickCloneFile,
    onGoDub,
  } = props;

  const locked = busy || downloadingUrl || cloningSegment;

  return (
    <section className={`panel clone-panel ${locked ? "settings-locked" : ""}`}>
      <h2>Clone đoạn video</h2>
      <p className="muted url-lead">
        Chọn video trên máy, nhập khoảng thời gian → tạo file clip mới. Không bắt buộc
        lồng tiếng; muốn thuyết minh thì sang tab Lồng tiếng sau.
      </p>

      <div className="row url-row">
        <label htmlFor="clone-source-path">Video nguồn</label>
        <input
          id="clone-source-path"
          value={cloneSource}
          readOnly
          placeholder="Chưa chọn video"
          disabled={locked}
        />
        <button type="button" onClick={onPickCloneFile} disabled={locked}>
          Chọn file
        </button>
      </div>

      {queue.length > 0 ? (
        <div className="row url-row">
          <label htmlFor="clone-source">Hoặc từ hàng đợi</label>
          <select
            id="clone-source"
            value={queue.some((q) => q.input === cloneSource) ? cloneSource : ""}
            onChange={(e) => onCloneSource(e.target.value)}
            disabled={locked}
          >
            <option value="">— Chọn từ hàng đợi —</option>
            {queue.map((item) => (
              <option key={`${item.index}-${item.input}`} value={item.input}>
                {item.stem}
                {item.duration_label ? ` (${item.duration_label})` : ""}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <div className="row url-row">
        <label htmlFor="clone-name">Tên video</label>
        <input
          id="clone-name"
          value={cloneName}
          onChange={(e) => onCloneName(e.target.value)}
          placeholder="vd: doan_gioi_thieu"
          disabled={locked}
        />
      </div>
      <div className="row clone-times">
        <label htmlFor="clone-start">Bắt đầu</label>
        <input
          id="clone-start"
          value={cloneStart}
          onChange={(e) => onCloneStart(e.target.value)}
          placeholder="0 hoặc 0:00"
          disabled={locked}
        />
        <label htmlFor="clone-end">Kết thúc</label>
        <input
          id="clone-end"
          value={cloneEnd}
          onChange={(e) => onCloneEnd(e.target.value)}
          placeholder="1:30 hoặc 90"
          disabled={locked}
        />
        <button
          type="button"
          className="primary"
          disabled={
            locked ||
            !cloneSource.trim() ||
            !cloneStart.trim() ||
            !cloneEnd.trim() ||
            !cloneName.trim()
          }
          onClick={onCloneSegment}
        >
          {cloningSegment ? "Đang cắt…" : "Cắt đoạn"}
        </button>
      </div>
      <p className="muted url-dir-hint">
        Thời gian: giây (90) hoặc MM:SS / HH:MM:SS. File lưu cạnh video nguồn với tên
        bạn đặt (tự thêm đuôi <code>.mp4</code>/<code>.mkv</code>… nếu bỏ trống đuôi).
        Clip mới cũng được thêm vào hàng đợi tab Lồng tiếng để dùng tiếp nếu cần.
      </p>
      <div className="actions" style={{ marginTop: 12 }}>
        <button type="button" onClick={onGoDub} disabled={locked}>
          Sang tab Lồng tiếng
        </button>
      </div>
    </section>
  );
}
