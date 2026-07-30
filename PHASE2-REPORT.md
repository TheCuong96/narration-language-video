# Phase 2 — Chức năng xử lý video

## Engine (`engine/dubvi`)

- Định dạng: MP4, MKV, MOV, AVI, WebM (`--files` và/hoặc `-i` folder)
- Hàng đợi tuần tự + `queue.json` theo job
- `cancel` / `retry` / resume cache (`--from-stage`)
- Review bản dịch: `--review` → `review-get` / `review-set` → `continue`
- Audio modes: `vi_only` | `dual_track` | `mix` (`--mix-db`)
- Mux: copy video stream khi được; emit `warning` `REENCODE_REQUIRED` nếu phải re-encode

### Ví dụ CLI

```powershell
cd engine
python -m dubvi run -f "D:\a.mp4" "D:\b.mkv" -o "D:\out" --review --audio-mode dual_track
python -m dubvi review-get --job-id <id> --stem a
python -m dubvi review-set --job-id <id> --stem a --file edited.json
python -m dubvi continue --job-id <id> --stem a
python -m dubvi cancel <id>
python -m dubvi retry --job-id <id>
```

## Desktop UI (`desktop/`)

- React + TypeScript: kéo-thả, hàng đợi, review, nhật ký dễ đọc, 3 chế độ audio
- Tauri v2 shell: spawn engine, dialog, mở folder, drag-drop paths
- Dev: `cd desktop && npm install && npm run tauri dev` (cần Rust + Python engine)

Tkinter cũ vẫn giữ nguyên.
