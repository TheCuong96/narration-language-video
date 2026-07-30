#!/usr/bin/env python3
"""
Dub VI — Desktop GUI for dubbing videos to Vietnamese.
Double-click friendly; uses dub_vi.py under the hood.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

DUB_SCRIPT = APP_DIR / "dub_vi.py"
DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
VOICES = [
    ("Nữ — Hoài My", "vi-VN-HoaiMyNeural"),
    ("Nam — Nam Minh", "vi-VN-NamMinhNeural"),
]
MODELS = ["tiny", "base", "small", "medium", "large-v3"]


class DubViApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dub VI — Lồng tiếng Việt cho video")
        self.geometry("780x620")
        self.minsize(700, 520)
        self.configure(bg="#f4f6f8")

        self.proc: subprocess.Popen | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self._build_ui()
        self.after(120, self._drain_log)
        self.after(200, self._auto_check_light)

    def _build_ui(self) -> None:
        pad = {"padx": 14, "pady": 6}
        header = tk.Frame(self, bg="#0f3d5c")
        header.pack(fill="x")
        tk.Label(
            header,
            text="Dub VI",
            font=("Segoe UI Semibold", 18),
            fg="white",
            bg="#0f3d5c",
        ).pack(side="left", padx=16, pady=12)
        tk.Label(
            header,
            text="Chọn folder video → Bấm Bắt đầu",
            font=("Segoe UI", 10),
            fg="#c9dceb",
            bg="#0f3d5c",
        ).pack(side="left", pady=12)

        body = tk.Frame(self, bg="#f4f6f8")
        body.pack(fill="both", expand=True, **pad)

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.voice_label = tk.StringVar(value=VOICES[0][0])
        self.model_var = tk.StringVar(value="medium")
        self.cpu_var = tk.BooleanVar(value=False)
        self.force_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Sẵn sàng")

        self._row_folder(body, "Thư mục video gốc (MP4)", self.in_var, 0)
        self._row_folder(body, "Thư mục lưu bản tiếng Việt", self.out_var, 1)

        opts = tk.LabelFrame(body, text=" Tuỳ chọn ", bg="#f4f6f8", font=("Segoe UI", 9))
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        body.grid_columnconfigure(1, weight=1)

        tk.Label(opts, text="Giọng đọc:", bg="#f4f6f8").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Combobox(
            opts,
            textvariable=self.voice_label,
            values=[v[0] for v in VOICES],
            state="readonly",
            width=28,
        ).grid(row=0, column=1, sticky="w", padx=4)

        tk.Label(opts, text="Model Whisper:", bg="#f4f6f8").grid(row=0, column=2, sticky="w", padx=8)
        ttk.Combobox(
            opts,
            textvariable=self.model_var,
            values=MODELS,
            state="readonly",
            width=12,
        ).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Checkbutton(opts, text="Chỉ dùng CPU (không GPU)", variable=self.cpu_var).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )
        ttk.Checkbutton(opts, text="Làm lại dù đã có file (force)", variable=self.force_var).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=8, pady=4
        )

        btns = tk.Frame(body, bg="#f4f6f8")
        btns.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)

        self.btn_setup = ttk.Button(btns, text="1. Kiểm tra / Cài đặt", command=self.run_setup)
        self.btn_setup.pack(side="left", padx=(0, 8))
        self.btn_start = ttk.Button(btns, text="2. Bắt đầu lồng tiếng", command=self.run_dub)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = ttk.Button(btns, text="Dừng", command=self.stop_job, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Mở thư mục kết quả", command=self.open_output).pack(side="left")

        log_frame = tk.LabelFrame(body, text=" Nhật ký ", bg="#f4f6f8")
        log_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        body.grid_rowconfigure(4, weight=1)

        self.log = tk.Text(
            log_frame,
            height=16,
            wrap="word",
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
        )
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        scroll = ttk.Scrollbar(self.log, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)

        status = tk.Frame(self, bg="#e8eef3")
        status.pack(fill="x", side="bottom")
        tk.Label(
            status,
            textvariable=self.status_var,
            anchor="w",
            bg="#e8eef3",
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=12, pady=6)

    def _row_folder(self, parent: tk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, bg="#f4f6f8", font=("Segoe UI", 9)).grid(
            row=row, column=0, sticky="w", pady=4
        )
        ent = ttk.Entry(parent, textvariable=var)
        ent.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

        def browse() -> None:
            path = filedialog.askdirectory(title=label)
            if path:
                var.set(path)
                if var is self.in_var and not self.out_var.get().strip():
                    self.out_var.set(str(Path(path).parent / (Path(path).name + "-vi")))

        ttk.Button(parent, text="Chọn...", command=browse).grid(row=row, column=2, pady=4)

    def _append(self, text: str) -> None:
        self.log.insert("end", text)
        self.log.see("end")

    def _drain_log(self) -> None:
        try:
            while True:
                self._append(self.log_q.get_nowait())
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.btn_setup.configure(state=state)
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state="normal" if busy else "disabled")

    def _voice_id(self) -> str:
        label = self.voice_label.get()
        for name, vid in VOICES:
            if name == label:
                return vid
        return DEFAULT_VOICE

    def _auto_check_light(self) -> None:
        self.log_q.put("Chào mừng! Bấm «Kiểm tra / Cài đặt» lần đầu, rồi chọn folder và Bắt đầu.\n")

    def _run_cmd(self, args: list[str], title: str) -> None:
        if self.proc and self.proc.poll() is None:
            messagebox.showwarning("Đang chạy", "Một tiến trình khác đang chạy. Hãy Dừng trước.")
            return
        if not DUB_SCRIPT.exists():
            messagebox.showerror("Lỗi", f"Không tìm thấy {DUB_SCRIPT}")
            return

        self._set_busy(True)
        self.status_var.set(title)
        self.log_q.put(f"\n—— {title} ——\n")
        cmd = [sys.executable, "-u", str(DUB_SCRIPT), *args]
        self.log_q.put("> " + " ".join(cmd) + "\n")

        def worker() -> None:
            try:
                creationflags = 0
                if sys.platform == "win32":
                    creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                assert self.proc.stdout is not None
                for line in self.proc.stdout:
                    self.log_q.put(line)
                code = self.proc.wait()
                if code == 0:
                    self.log_q.put("\n✓ Hoàn tất.\n")
                    self.status_var.set("Hoàn tất")
                else:
                    self.log_q.put(f"\n✗ Kết thúc với mã lỗi {code}\n")
                    self.status_var.set(f"Lỗi (code {code})")
            except Exception as e:
                self.log_q.put(f"\n✗ {e}\n")
                self.status_var.set("Lỗi")
            finally:
                self.proc = None
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def run_setup(self) -> None:
        args = ["--setup"]
        if self.cpu_var.get():
            args.append("--cpu")
        self._run_cmd(args, "Kiểm tra / cài đặt dependency")

    def run_dub(self) -> None:
        inp = self.in_var.get().strip()
        out = self.out_var.get().strip()
        if not inp or not Path(inp).is_dir():
            messagebox.showerror("Thiếu thư mục", "Hãy chọn thư mục video gốc chứa file .mp4")
            return
        if not out:
            messagebox.showerror("Thiếu thư mục", "Hãy chọn thư mục lưu bản tiếng Việt")
            return

        args = [
            "-i",
            inp,
            "-o",
            out,
            "--voice",
            self._voice_id(),
            "--model",
            self.model_var.get(),
        ]
        if self.cpu_var.get():
            args.append("--cpu")
        if self.force_var.get():
            args.append("--force")
        self._run_cmd(args, "Đang lồng tiếng Việt…")

    def stop_job(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.log_q.put("\n… Đã gửi lệnh dừng.\n")
            self.status_var.set("Đã dừng")

    def open_output(self) -> None:
        out = self.out_var.get().strip()
        if not out or not Path(out).exists():
            messagebox.showinfo("Chưa có", "Thư mục kết quả chưa tồn tại.")
            return
        if sys.platform == "win32":
            os.startfile(out)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", out])


def main() -> int:
    app = DubViApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
