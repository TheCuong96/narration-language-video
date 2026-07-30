import type { FriendlyError } from "../lib/types";

interface Props {
  open: boolean;
  friendly?: FriendlyError | null;
  technical: string;
  onClose: () => void;
}

export function ErrorDialog({ open, friendly, technical, onClose }: Props) {
  if (!open) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(technical);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <h3>{friendly?.title || "Đã xảy ra lỗi"}</h3>
        <p className="modal-body">{friendly?.body || "Có lỗi khi xử lý."}</p>
        {friendly?.hint ? <p className="modal-hint">{friendly.hint}</p> : null}
        <details className="tech-details">
          <summary>Xem chi tiết kỹ thuật</summary>
          <pre>{technical}</pre>
        </details>
        <div className="actions">
          <button type="button" onClick={copy}>
            Sao chép log
          </button>
          <button type="button" className="primary" onClick={onClose}>
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
