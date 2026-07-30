# Dub VI — Lồng tiếng Việt cho video

## Cách dễ nhất: cài như app Desktop

Trong PowerShell (tại thư mục project):

```powershell
cd C:\Users\user\Desktop\banking
powershell -ExecutionPolicy Bypass -File tools\install_desktop_app.ps1
```

Script sẽ:
1. Copy tool vào `%LOCALAPPDATA%\Programs\DubVI`
2. Tự kiểm tra / cài Python packages + FFmpeg nếu thiếu
3. Tạo shortcut **Dub VI** trên Desktop và Start Menu

Sau đó mở app như phần mềm bình thường → chọn folder video → **Bắt đầu**.

Gỡ cài đặt:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DubVI\Uninstall-DubVI.ps1"
```

Hoặc chạy tạm không cần cài:

```powershell
tools\DubVI.bat
```

---

## Trong app (GUI)

1. Bấm **Kiểm tra / Cài đặt** (lần đầu)
2. **Chọn** thư mục chứa file `.mp4` gốc
3. **Chọn** thư mục lưu bản tiếng Việt (tự gợi ý `...-vi`)
4. Bấm **Bắt đầu lồng tiếng**
5. Xem nhật ký; khi xong bấm **Mở thư mục kết quả**

---

## Dùng bằng dòng lệnh (nâng cao)

```powershell
python tools\dub_vi.py --setup
python tools\dub_vi.py -i "D:\videos\en" -o "D:\videos\vi"
python tools\dub_vi.py --list-voices
```

| Flag | Ý nghĩa |
|------|---------|
| `-i` / `-o` | Folder vào / ra |
| `--only` | Chỉ vài file |
| `--voice` | `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural` |
| `--cpu` | Không dùng GPU |
| `--force` | Làm lại dù đã có output |
| `--setup` | Chỉ check/cài dependency |

Chi tiết CLI: xem phần còn lại trong repo hoặc `python tools\dub_vi.py -h`.

---

## File trong bộ tool

| File | Vai trò |
|------|---------|
| `dub_vi_gui.py` | Giao diện Desktop |
| `install_desktop_app.ps1` | Cài app + shortcut |
| `DubVI.bat` | Mở GUI nhanh |
| `dub_vi.py` | Engine xử lý video |
| `dub_deps.py` | Tự check / cài dependency |
| `requirements-dub.txt` | Danh sách package Python |

---

## Lưu ý

- Cần **Python 3.10+** (tick Add to PATH khi cài).
- Cần **Internet** khi dịch và tạo giọng.
- Video gốc không bị sửa.
- Video dài có thể mất nhiều thời gian (TTS từng đoạn).
