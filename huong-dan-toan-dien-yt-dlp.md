# Hướng dẫn toàn diện về `yt-dlp`

> Sổ tay sử dụng thực tế dành cho Windows và cho ứng dụng xử lý/thuyết minh video  
> Cập nhật nội dung: 31/07/2026

## Mục lục

1. [`yt-dlp` là gì?](#1-yt-dlp-là-gì)
2. [Vai trò trong công cụ thuyết minh video](#2-vai-trò-trong-công-cụ-thuyết-minh-video)
3. [Cú pháp và quy tắc cơ bản](#3-cú-pháp-và-quy-tắc-cơ-bản)
4. [Kiểm tra, cập nhật và xem trợ giúp](#4-kiểm-tra-cập-nhật-và-xem-trợ-giúp)
5. [Tải video](#5-tải-video)
6. [Xem và chọn chất lượng/định dạng](#6-xem-và-chọn-chất-lượngđịnh-dạng)
7. [Tải hoặc chuyển đổi âm thanh](#7-tải-hoặc-chuyển-đổi-âm-thanh)
8. [Xử lý playlist, kênh và nhiều URL](#8-xử-lý-playlist-kênh-và-nhiều-url)
9. [Phụ đề](#9-phụ-đề)
10. [Thumbnail và dữ liệu đi kèm](#10-thumbnail-và-dữ-liệu-đi-kèm)
11. [Tên file và thư mục lưu](#11-tên-file-và-thư-mục-lưu)
12. [Lọc video trước khi tải](#12-lọc-video-trước-khi-tải)
13. [Cắt đoạn và xử lý chapter](#13-cắt-đoạn-và-xử-lý-chapter)
14. [Livestream và video được lên lịch](#14-livestream-và-video-được-lên-lịch)
15. [Điều khiển tốc độ, retry và tải song song](#15-điều-khiển-tốc-độ-retry-và-tải-song-song)
16. [Mạng, proxy, header và mô phỏng trình duyệt](#16-mạng-proxy-header-và-mô-phỏng-trình-duyệt)
17. [Cookie và nội dung yêu cầu đăng nhập](#17-cookie-và-nội-dung-yêu-cầu-đăng-nhập)
18. [Hậu xử lý bằng FFmpeg](#18-hậu-xử-lý-bằng-ffmpeg)
19. [Metadata, thumbnail, chapter nhúng trong file](#19-metadata-thumbnail-chapter-nhúng-trong-file)
20. [SponsorBlock](#20-sponsorblock)
21. [Chế độ xem thông tin, JSON và kiểm thử](#21-chế-độ-xem-thông-tin-json-và-kiểm-thử)
22. [Cấu hình mặc định bằng `yt-dlp.conf`](#22-cấu-hình-mặc-định-bằng-yt-dlpconf)
23. [Tích hợp `yt-dlp` vào ứng dụng desktop](#23-tích-hợp-yt-dlp-vào-ứng-dụng-desktop)
24. [Các lệnh mẫu thực tế](#24-các-lệnh-mẫu-thực-tế)
25. [Lỗi thường gặp và cách xử lý](#25-lỗi-thường-gặp-và-cách-xử-lý)
26. [Giới hạn, an toàn và bản quyền](#26-giới-hạn-an-toàn-và-bản-quyền)
27. [Bảng tra cứu nhanh](#27-bảng-tra-cứu-nhanh)

---

## 1. `yt-dlp` là gì?

`yt-dlp` là công cụ dòng lệnh mã nguồn mở dùng để:

- Lấy thông tin video từ URL.
- Tải video và âm thanh từ YouTube cùng nhiều website được hỗ trợ khác.
- Chọn độ phân giải, codec, container và luồng âm thanh mong muốn.
- Tải playlist, nội dung của kênh, phụ đề, thumbnail và metadata.
- Gọi FFmpeg để ghép, chuyển đổi hoặc hậu xử lý file sau khi tải.
- Xuất dữ liệu JSON để phần mềm khác tiếp tục xử lý.

`yt-dlp` không phải trình chỉnh sửa video và không có giao diện đồ họa chính thức. Người dùng thường chạy nó bằng PowerShell/Terminal, hoặc ứng dụng desktop gọi tiến trình `yt-dlp` ở phía sau.

Tài liệu này bao phủ toàn bộ **nhóm chức năng xử lý chính** mà người dùng và ứng dụng desktop thường cần. Nó không lặp lại mọi alias cũ, mọi tùy chọn `--no-*`, tùy chọn dành riêng cho nhà phát triển hoặc hàng trăm tham số đặc thù của từng website. Danh sách option tuyệt đối đầy đủ của đúng phiên bản đang cài luôn được lấy bằng `yt-dlp --help`.

### `yt-dlp` không trực tiếp làm những việc nào?

| Công việc | Công cụ phù hợp |
|---|---|
| Nhận dạng lời nói thành văn bản | Whisper hoặc hệ thống speech-to-text |
| Dịch lời nói sang tiếng Việt | Dịch vụ/mô hình dịch |
| Tạo giọng đọc tiếng Việt | `edge-tts` hoặc dịch vụ TTS khác |
| Tách giọng nói khỏi nhạc nền | Demucs, MDX-Net hoặc công cụ tương tự |
| Dựng, ghép và chuyển mã video | FFmpeg |
| Tải video, âm thanh, phụ đề, metadata từ URL | `yt-dlp` |

---

## 2. Vai trò trong công cụ thuyết minh video

Trong công cụ dịch và thuyết minh video, `yt-dlp` chỉ nên chịu trách nhiệm lấy dữ liệu đầu vào:

1. Người dùng dán URL video.
2. Ứng dụng gọi `yt-dlp` để kiểm tra URL và lấy metadata.
3. Người dùng chọn chất lượng hoặc ứng dụng tự chọn cấu hình phù hợp.
4. `yt-dlp` tải video/âm thanh về thư mục tạm.
5. FFmpeg tách hoặc chuẩn hóa âm thanh.
6. Whisper nhận dạng lời nói.
7. Hệ thống dịch văn bản sang tiếng Việt.
8. TTS tạo giọng thuyết minh.
9. FFmpeg ghép âm thanh mới với video.
10. Ứng dụng đưa file hoàn chỉnh vào thư mục xuất.

Đầu ra quan trọng của `yt-dlp` cho ứng dụng gồm:

- Đường dẫn file đã tải.
- Tiêu đề, ID, thời lượng và tên kênh.
- Thumbnail.
- Danh sách định dạng/độ phân giải.
- Phụ đề nếu có.
- Trạng thái và phần trăm tải.
- Mã thoát và nội dung lỗi.

---

## 3. Cú pháp và quy tắc cơ bản

Cú pháp tổng quát:

```powershell
yt-dlp [TÙY_CHỌN] "URL"
```

Ví dụ:

```powershell
yt-dlp "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Quy tắc nên nhớ

- Luôn đặt URL trong dấu ngoặc kép, nhất là khi URL chứa `&`, `?` hoặc ký tự đặc biệt.
- Có thể truyền nhiều URL trong một lệnh.
- Tùy chọn có thể đặt trước URL; đây là cách dễ đọc nhất.
- Không tự thêm phần mở rộng cố định vào `-o`; hãy dùng `%(ext)s` để `yt-dlp` chọn đúng đuôi file.
- Các lệnh trong tài liệu này dùng cú pháp PowerShell. Khi viết file `.bat`, ký tự `%` trong output template phải viết thành `%%`.

Ví dụ truyền nhiều URL:

```powershell
yt-dlp "URL_1" "URL_2" "URL_3"
```

---

## 4. Kiểm tra, cập nhật và xem trợ giúp

### Kiểm tra phiên bản

```powershell
yt-dlp --version
```

Giúp xác nhận lệnh đang gọi đúng bản `yt-dlp` và cung cấp thông tin khi báo lỗi.

### Xem toàn bộ tùy chọn của phiên bản đang cài

```powershell
yt-dlp --help
```

Đây là danh sách đầy đủ và chính xác nhất đối với phiên bản hiện tại. `yt-dlp` thay đổi thường xuyên, nên một tài liệu tĩnh không thể thay thế hoàn toàn `--help`.

### Cập nhật bản executable chính thức

```powershell
yt-dlp -U
```

Nếu cài bằng `pip`, cập nhật bằng trình quản lý package đã dùng để cài:

```powershell
python -m pip install -U yt-dlp
```

### Chuyển kênh cập nhật

```powershell
yt-dlp --update-to nightly
```

- `stable`: phù hợp với người dùng thông thường.
- `nightly`: có bản sửa mới sớm hơn, hữu ích khi website vừa thay đổi.
- `master`: mã phát triển mới nhất, không nên là mặc định cho người dùng phổ thông.

### Liệt kê extractor

```powershell
yt-dlp --list-extractors
```

Extractor là bộ phận hiểu cấu trúc của từng website. Có extractor riêng cho YouTube, Vimeo, SoundCloud và nhiều dịch vụ khác.

---

## 5. Tải video

### Tải theo cấu hình mặc định

```powershell
yt-dlp "URL"
```

`yt-dlp` tự chọn định dạng tốt theo quy tắc mặc định. Khi video tốt nhất và âm thanh tốt nhất nằm ở hai luồng riêng, FFmpeg được dùng để ghép chúng.

### Tải và ưu tiên file MP4 dễ phát

```powershell
yt-dlp -t mp4 "URL"
```

Preset `mp4` ưu tiên codec/container có khả năng tương thích tốt và remux đầu ra sang MP4 khi phù hợp.

### Tải tối đa 1080p

```powershell
yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 "URL"
```

Ý nghĩa:

- `bv*`: định dạng tốt nhất có hình ảnh; có thể đã kèm âm thanh.
- `ba`: âm thanh tốt nhất.
- `+`: ghép các luồng.
- `/`: phương án dự phòng nếu lựa chọn phía trước không có.
- `[height<=1080]`: không vượt quá 1080p.

### Tải luồng video và audio thành hai file riêng

```powershell
yt-dlp -f "bv,ba" -o "%(title)s.f%(format_id)s.%(ext)s" "URL"
```

Hữu ích khi ứng dụng muốn xử lý riêng video gốc và âm thanh gốc.

### Tải lại từ phần đã dừng

Mặc định, `yt-dlp` có thể tiếp tục file tải dở khi còn file `.part`. Không xóa file `.part` nếu muốn resume.

Các tùy chọn liên quan:

- `--continue`: tiếp tục tải file còn dang dở; đây thường là mặc định.
- `--no-continue`: không nối tiếp file cũ.
- `--part`: dùng file tạm có đuôi `.part`.
- `--no-part`: ghi trực tiếp vào file đích; tăng rủi ro để lại file hỏng nếu bị ngắt.

---

## 6. Xem và chọn chất lượng/định dạng

### Liệt kê các định dạng có sẵn

```powershell
yt-dlp -F "URL"
```

Bảng kết quả thường có:

- `ID`: mã định dạng.
- `EXT`: container như mp4, webm, m4a.
- Độ phân giải.
- FPS.
- Codec video và audio.
- Bitrate hoặc dung lượng ước tính.
- Giao thức tải như HTTPS, HLS hoặc DASH.

### Tải theo ID định dạng

```powershell
yt-dlp -f "137+140" "URL"
```

Trong ví dụ này, `137` và `140` chỉ là ID minh họa. ID thực tế thay đổi theo từng video; luôn xem bằng `-F` trước.

### Chọn định dạng tốt nhất

```powershell
yt-dlp -f "bv+ba/b" "URL"
```

- `bv`: video-only tốt nhất.
- `ba`: audio-only tốt nhất.
- `b`: file tốt nhất đã có cả video và audio.

### Giới hạn độ phân giải

```powershell
yt-dlp -S "res:720" "URL"
```

`-S` sắp xếp định dạng và ưu tiên độ phân giải không vượt quá giá trị mong muốn nếu có lựa chọn phù hợp.

Các ví dụ khác:

```powershell
# Tối đa 480p
yt-dlp -S "res:480" "URL"

# Ưu tiên file nhỏ
yt-dlp -S "+size,+br" "URL"

# Ưu tiên phần mở rộng/container phù hợp
yt-dlp -S "ext" "URL"
```

### Giới hạn dung lượng

```powershell
yt-dlp -f "b[filesize<50M]/w" "URL"
```

Lệnh chọn file có cả hình và tiếng dưới 50 MB nếu có, nếu không sẽ dùng phương án chất lượng thấp hơn. `filesize` đôi khi không được website cung cấp; có thể dùng `filesize_approx` trong bộ lọc nâng cao.

### Chọn codec và khả năng tương thích

Ví dụ ưu tiên video H.264 và audio AAC:

```powershell
yt-dlp -S "vcodec:h264,acodec:aac,res,br" --merge-output-format mp4 "URL"
```

Lưu ý: remux chỉ thay container, không biến codec VP9/AV1 thành H.264. Nếu bắt buộc đổi codec, phải re-encode bằng FFmpeg và sẽ tốn CPU/thời gian.

### Nhiều luồng audio/video

- `--audio-multistreams`: cho phép ghép nhiều luồng audio vào một file.
- `--video-multistreams`: cho phép ghép nhiều luồng video.

Tính năng này phù hợp với file MKV hoặc quy trình chuyên biệt; không cần bật cho tải video thông thường.

---

## 7. Tải hoặc chuyển đổi âm thanh

### Chỉ lấy audio và chuyển thành MP3

```powershell
yt-dlp -x --audio-format mp3 "URL"
```

Preset ngắn tương đương:

```powershell
yt-dlp -t mp3 "URL"
```

### Chọn chất lượng MP3

```powershell
yt-dlp -x --audio-format mp3 --audio-quality 0 "URL"
```

- Với VBR, `0` là tốt nhất và `10` là thấp nhất.
- Có thể dùng bitrate cụ thể như `128K`, `192K` hoặc `320K`.

```powershell
yt-dlp -x --audio-format mp3 --audio-quality 192K "URL"
```

### Các định dạng audio thường dùng

| Định dạng | Mục đích |
|---|---|
| `mp3` | Tương thích rộng, dung lượng vừa phải |
| `m4a`/AAC | Phổ biến, chất lượng tốt ở bitrate vừa |
| `opus` | Hiệu quả nén tốt, không phải thiết bị nào cũng hỗ trợ như MP3 |
| `wav` | Không nén, dung lượng rất lớn, phù hợp xử lý âm thanh |
| `flac` | Lossless, dung lượng nhỏ hơn WAV nhưng vẫn lớn |

### Lấy audio gốc mà không chuyển mã không cần thiết

```powershell
yt-dlp -f "ba" "URL"
```

Lệnh này tải luồng audio tốt nhất ở định dạng nguồn, chẳng hạn `.m4a`, `.webm` hoặc `.opus`. Đây thường là lựa chọn tốt cho pipeline Whisper vì tránh một lần mã hóa mất dữ liệu không cần thiết; sau đó FFmpeg có thể chuẩn hóa sang WAV mono 16 kHz nếu mô hình cần.

---

## 8. Xử lý playlist, kênh và nhiều URL

### Tải playlist

```powershell
yt-dlp "URL_PLAYLIST"
```

### Chỉ tải video hiện tại, không tải cả playlist

```powershell
yt-dlp --no-playlist "URL"
```

Đây là tùy chọn quan trọng khi URL video có kèm tham số playlist.

### Chủ động tải playlist

```powershell
yt-dlp --yes-playlist "URL"
```

### Chọn một số phần tử

```powershell
# Video thứ 1, 3 và từ 5 đến 8
yt-dlp --playlist-items "1,3,5:8" "URL_PLAYLIST"
```

### Giới hạn theo vị trí

```powershell
yt-dlp --playlist-start 5 --playlist-end 10 "URL_PLAYLIST"
```

### Đảo thứ tự hoặc tải ngẫu nhiên

```powershell
yt-dlp --playlist-reverse "URL_PLAYLIST"
yt-dlp --playlist-random "URL_PLAYLIST"
```

### Chỉ lấy cấu trúc playlist nhanh

```powershell
yt-dlp --flat-playlist --dump-json "URL_PLAYLIST"
```

`--flat-playlist` tránh trích xuất sâu từng video, nên nhanh hơn nhưng một số metadata có thể thiếu và không phù hợp khi cần tải đầy đủ ngay.

### Xử lý playlist theo kiểu streaming

```powershell
yt-dlp --lazy-playlist "URL_PLAYLIST"
```

`--lazy-playlist` xử lý mục ngay khi nhận được thay vì chờ phân tích toàn playlist. Một số tính năng cần biết toàn bộ danh sách như random/reverse sẽ không dùng được.

### Không tải lại video cũ

```powershell
yt-dlp --download-archive archive.txt "URL_PLAYLIST"
```

Sau mỗi lượt tải thành công, ID video được ghi vào `archive.txt`. Những lần chạy sau sẽ bỏ qua ID đã tồn tại. Đây là cách tốt để đồng bộ video mới của playlist/kênh.

### File chứa nhiều URL

Tạo `urls.txt`, mỗi dòng một URL, sau đó chạy:

```powershell
yt-dlp -a urls.txt
```

Các dòng bắt đầu bằng ký tự comment được bỏ qua theo quy tắc của `yt-dlp`.

### Kiểm soát lỗi trong playlist

- `--ignore-errors`: tiếp tục xử lý mục sau khi một mục lỗi.
- `--abort-on-error`: dừng toàn bộ khi gặp lỗi.
- `--skip-playlist-after-errors N`: bỏ phần còn lại sau N lỗi.
- `--max-downloads N`: dừng sau N file tải thành công/được xử lý theo giới hạn.
- `--break-on-existing`: dừng khi gặp video đã có trong archive.

---

## 9. Phụ đề

### Xem danh sách phụ đề

```powershell
yt-dlp --list-subs "URL"
```

### Tải phụ đề do tác giả cung cấp

```powershell
yt-dlp --write-subs --sub-langs "vi,en" --skip-download "URL"
```

### Tải phụ đề tự động

```powershell
yt-dlp --write-auto-subs --sub-langs "vi,en" --skip-download "URL"
```

`--write-auto-subs` lấy phụ đề tự động nếu nền tảng cung cấp. Đây không phải Whisper chạy trên máy của bạn.

### Chọn định dạng phụ đề

```powershell
yt-dlp --write-subs --sub-langs "vi" --sub-format "srt/best" --skip-download "URL"
```

### Chuyển phụ đề sang SRT

```powershell
yt-dlp --write-subs --sub-langs "vi" --convert-subs srt --skip-download "URL"
```

Việc chuyển định dạng cần FFmpeg trong các trường hợp tương ứng.

### Nhúng phụ đề vào video

```powershell
yt-dlp --write-subs --sub-langs "vi" --embed-subs "URL"
```

Nhúng subtitle tạo track có thể bật/tắt trong trình phát; không phải đốt chữ cố định lên hình. Muốn hard-sub phải dùng bộ lọc subtitle của FFmpeg.

### Tải mọi ngôn ngữ nhưng bỏ live chat

```powershell
yt-dlp --write-subs --sub-langs "all,-live_chat" "URL"
```

---

## 10. Thumbnail và dữ liệu đi kèm

### Liệt kê thumbnail

```powershell
yt-dlp --list-thumbnails "URL"
```

### Tải thumbnail

```powershell
yt-dlp --write-thumbnail --skip-download "URL"
```

### Tải tất cả thumbnail

```powershell
yt-dlp --write-all-thumbnails --skip-download "URL"
```

### Chuyển thumbnail sang JPG

```powershell
yt-dlp --write-thumbnail --convert-thumbnails jpg --skip-download "URL"
```

### Tải description

```powershell
yt-dlp --write-description --skip-download "URL"
```

### Lưu metadata dạng JSON

```powershell
yt-dlp --write-info-json --skip-download "URL"
```

File `.info.json` có thể chứa tiêu đề, thời lượng, uploader, thumbnail, format, chapter và nhiều trường khác. Không nên công khai file này mà chưa kiểm tra vì tùy extractor nó có thể chứa URL tạm thời hoặc thông tin không cần chia sẻ.

### Lưu comment

```powershell
yt-dlp --write-comments --write-info-json --skip-download "URL"
```

Việc lấy comment có thể rất chậm, tạo nhiều request và không phải website nào cũng hỗ trợ.

---

## 11. Tên file và thư mục lưu

### Chọn thư mục tải

```powershell
yt-dlp -P "D:\Videos" "URL"
```

### Tùy chỉnh tên file

```powershell
yt-dlp -o "%(title)s [%(id)s].%(ext)s" "URL"
```

### Tách theo tên kênh

```powershell
yt-dlp -P "D:\Videos" -o "%(uploader)s\%(title)s [%(id)s].%(ext)s" "URL"
```

### Tách playlist thành thư mục riêng

```powershell
yt-dlp -P "D:\Videos" -o "%(playlist_title)s\%(playlist_index)03d - %(title)s.%(ext)s" "URL_PLAYLIST"
```

### Thư mục tạm và thư mục đầu ra

```powershell
yt-dlp -P "temp:D:\VideoTemp" -P "home:D:\Videos" "URL"
```

File trung gian tải vào `temp`, sau khi hoàn tất mới được chuyển đến `home`. Cách này phù hợp với ứng dụng desktop vì tránh để người dùng thấy file chưa hoàn chỉnh trong thư mục đầu ra.

### Các trường output template thường dùng

| Trường | Ý nghĩa |
|---|---|
| `%(title)s` | Tiêu đề |
| `%(id)s` | ID video |
| `%(ext)s` | Phần mở rộng cuối cùng |
| `%(uploader)s` | Tên người/kênh đăng |
| `%(channel)s` | Tên kênh nếu extractor cung cấp |
| `%(upload_date)s` | Ngày đăng dạng `YYYYMMDD` |
| `%(duration)s` | Thời lượng tính bằng giây |
| `%(playlist_title)s` | Tên playlist |
| `%(playlist_index)03d` | Vị trí, thêm số 0 để đủ 3 chữ số |
| `%(format_id)s` | ID định dạng đã chọn |

### Tên file an toàn trên Windows

```powershell
yt-dlp --windows-filenames --trim-filenames 180 "URL"
```

- `--windows-filenames`: loại/sửa ký tự không hợp lệ trên Windows.
- `--trim-filenames N`: giới hạn chiều dài phần tên, không tính extension.
- `--restrict-filenames`: chỉ dùng ký tự ASCII đơn giản; có thể làm mất dấu tiếng Việt nên không phải lúc nào cũng phù hợp.

### Tránh ghi đè

- `--no-overwrites`: không ghi đè file đã có.
- `--force-overwrites`: ghi đè các file đầu ra và tắt resume.
- `--no-post-overwrites`: không ghi đè file hậu xử lý.

---

## 12. Lọc video trước khi tải

### Lọc theo thời lượng

```powershell
yt-dlp --match-filters "duration <= 600" "URL_PLAYLIST"
```

Chỉ tải video dài tối đa 10 phút.

### Bỏ livestream

```powershell
yt-dlp --match-filters "!is_live" "URL"
```

### Lọc theo lượt xem

```powershell
yt-dlp --match-filters "view_count >= 10000" "URL_PLAYLIST"
```

### Kết hợp điều kiện

```powershell
yt-dlp --match-filters "!is_live & duration < 1800" "URL_PLAYLIST"
```

### Hỏi người dùng trước mỗi video

```powershell
yt-dlp --match-filters - "URL_PLAYLIST"
```

### Một số bộ lọc lựa chọn khác

- `--date DATE`: video được tải lên đúng ngày.
- `--datebefore DATE`: trước ngày.
- `--dateafter DATE`: sau ngày.
- `--min-views N`, `--max-views N`: lọc lượt xem.
- `--min-filesize SIZE`, `--max-filesize SIZE`: lọc kích thước ước tính/biết trước.
- `--age-limit YEARS`: chỉ tải nội dung phù hợp mức tuổi đã chỉ định.
- `--match-title REGEX`, `--reject-title REGEX`: lọc tiêu đề bằng regex.

Không phải extractor nào cũng cung cấp đầy đủ metadata trước khi tải. Khi thiếu trường, hành vi của bộ lọc có thể khác kỳ vọng; hãy kiểm tra bằng `--simulate --print` trước.

---

## 13. Cắt đoạn và xử lý chapter

### Chỉ tải một khoảng thời gian

```powershell
yt-dlp --download-sections "*00:01:30-00:03:00" "URL"
```

Tải đoạn từ 1 phút 30 giây đến 3 phút. Tính năng cần FFmpeg.

### Tải từ một thời điểm đến hết

```powershell
yt-dlp --download-sections "*10:00-inf" "URL"
```

### Chọn chapter bằng regex

```powershell
yt-dlp --download-sections "intro" "URL"
```

Lệnh chọn chapter có tên khớp regex `intro` nếu video có dữ liệu chapter.

### Tách chapter thành các file

```powershell
yt-dlp --split-chapters "URL"
```

### Giữ chapter trong file

```powershell
yt-dlp --embed-chapters "URL"
```

### Lưu ý độ chính xác khi cắt

Cắt mà không re-encode thường phải bám keyframe nên điểm bắt đầu/kết thúc có thể lệch nhẹ. Nếu cần chính xác từng khung hình, pipeline riêng của FFmpeg phải re-encode đoạn cần thiết; thao tác này tốn thời gian và CPU hơn.

---

## 14. Livestream và video được lên lịch

### Tải livestream từ thời điểm hiện tại

```powershell
yt-dlp "URL_LIVESTREAM"
```

Đây thường là hành vi mặc định.

### Thử tải từ đầu livestream

```powershell
yt-dlp --live-from-start "URL_LIVESTREAM"
```

Tính năng này đang ở trạng thái thử nghiệm và chỉ hỗ trợ một số extractor.

### Chờ video được lên lịch bắt đầu

```powershell
yt-dlp --wait-for-video 30-60 "URL"
```

`yt-dlp` kiểm tra lại sau khoảng thời gian ngẫu nhiên từ 30 đến 60 giây.

### Dùng MPEG-TS khi tải HLS/live

```powershell
yt-dlp --hls-use-mpegts "URL_LIVESTREAM"
```

MPEG-TS có khả năng chịu gián đoạn tốt hơn và đôi khi phát được ngay khi đang tải. Đây thường là mặc định cho livestream.

---

## 15. Điều khiển tốc độ, retry và tải song song

### Tải nhiều fragment song song

```powershell
yt-dlp -N 4 "URL"
```

`-N 4` tải đồng thời 4 fragment đối với luồng DASH/HLS hỗ trợ. Số quá cao có thể gây lỗi, bị giới hạn hoặc tạo tải không cần thiết cho máy chủ.

### Giới hạn tốc độ

```powershell
yt-dlp --limit-rate 5M "URL"
```

Giới hạn xấp xỉ 5 MB/s theo đơn vị mà công cụ chấp nhận.

### Retry

```powershell
yt-dlp --retries 10 --fragment-retries 10 "URL"
```

- `--retries`: thử lại lỗi tải chính.
- `--fragment-retries`: thử lại fragment.
- `--file-access-retries`: thử lại khi file bị khóa/không truy cập được.
- Có thể dùng `infinite`, nhưng ứng dụng desktop nên đặt giới hạn để job không bị treo vô thời hạn.

### Điều chỉnh thời gian giữa các lần thử

```powershell
yt-dlp --retry-sleep "exp=1:20" "URL"
```

Exponential backoff giúp tránh gửi request liên tục khi server đang lỗi hoặc giới hạn.

### Nghỉ giữa các request/video

```powershell
yt-dlp --sleep-requests 1 --sleep-interval 5 --max-sleep-interval 10 "URL_PLAYLIST"
```

Giảm tốc độ request giúp hạn chế lỗi rate-limit. Preset có sẵn:

```powershell
yt-dlp -t sleep "URL_PLAYLIST"
```

### Dùng downloader ngoài

```powershell
yt-dlp --downloader aria2c --downloader-args "aria2c:-x 8 -s 8" "URL"
```

Các downloader ngoài được hỗ trợ tùy phiên bản có thể gồm `aria2c`, `curl`, `wget`, `ffmpeg` và công cụ khác. Chỉ nên dùng khi đã cài và hiểu công cụ đó; downloader mặc định đủ cho phần lớn nhu cầu.

---

## 16. Mạng, proxy, header và mô phỏng trình duyệt

### Dùng proxy

```powershell
yt-dlp --proxy "http://127.0.0.1:8080" "URL"
```

### Không dùng proxy hệ thống

```powershell
yt-dlp --proxy "" "URL"
```

### Chọn IPv4 hoặc IPv6

```powershell
yt-dlp -4 "URL"
yt-dlp -6 "URL"
```

Hữu ích khi một giao thức IP của mạng hiện tại hoạt động không ổn định.

### Đặt timeout

```powershell
yt-dlp --socket-timeout 30 "URL"
```

### Thêm HTTP header

```powershell
yt-dlp --add-headers "Referer:https://example.com/" "URL"
```

Chỉ thêm header khi website thực sự yêu cầu. Không sao chép token/header bí mật vào log hoặc giao diện.

### Mô phỏng client trình duyệt

Một số phiên bản/hệ thống hỗ trợ `--impersonate` để mô phỏng đặc điểm HTTP của client tương thích. Hãy xem danh sách client của bản đang cài:

```powershell
yt-dlp --list-impersonate-targets
```

Sau đó mới chọn target phù hợp. Tính năng có thể cần dependency bổ sung và không đảm bảo vượt được hệ thống chống bot.

### Không nên dùng tùy tiện

- `--no-check-certificates`: tắt kiểm tra chứng chỉ HTTPS, làm giảm an toàn.
- `--prefer-insecure`: ưu tiên kết nối không mã hóa.

Chỉ dùng trong môi trường kiểm thử có kiểm soát, không đặt làm cấu hình mặc định cho ứng dụng production.

---

## 17. Cookie và nội dung yêu cầu đăng nhập

### Đọc cookie trực tiếp từ trình duyệt

```powershell
yt-dlp --cookies-from-browser chrome "URL"
```

Trình duyệt khác có thể là `firefox`, `edge`, `brave`... tùy hệ thống và phiên bản.

### Dùng file cookie Netscape

```powershell
yt-dlp --cookies cookies.txt "URL"
```

### Khi nào mới cần cookie?

- Video riêng tư mà tài khoản được cấp quyền.
- Video giới hạn độ tuổi.
- Nội dung thành viên mà tài khoản có quyền xem.
- Website yêu cầu đăng nhập hợp lệ.
- Một số trường hợp CAPTCHA/anti-bot sau khi người dùng đã xác minh trong trình duyệt.

### Cảnh báo bảo mật quan trọng

- Cookie có thể cho phép truy cập tài khoản như một phiên đăng nhập. Không gửi file cookie cho người khác.
- Không ghi cookie vào log, database dạng plain text hoặc crash report.
- Không đóng gói cookie cá nhân của nhà phát triển trong ứng dụng.
- Chỉ dùng cookie của chính người dùng và khi họ hiểu mục đích.
- Việc dùng tài khoản với công cụ tự động có thể khiến tài khoản bị giới hạn hoặc khóa tạm thời/vĩnh viễn.
- Với ứng dụng desktop, nên để `yt-dlp` đọc cookie từ browser theo yêu cầu; không tự sao chép và lưu dài hạn nếu không cần.

### Lưu ý riêng với YouTube hiện tại

YouTube thường xuyên thay đổi cơ chế phát video, thử thách JavaScript và PO Token. Một số định dạng có thể thiếu hoặc trả lỗi 403 nếu môi trường chưa có JavaScript runtime/challenge solver hoặc PO Token phù hợp. Không nên hướng dẫn người dùng tự chép PO Token thủ công như một cấu hình cố định; tài liệu chính thức hiện khuyến nghị dùng provider plugin đáng tin cậy khi thật sự cần.

---

## 18. Hậu xử lý bằng FFmpeg

### FFmpeg có vai trò gì?

`yt-dlp` tải dữ liệu; FFmpeg đảm nhiệm các thao tác media như:

- Ghép video-only và audio-only.
- Trích xuất audio.
- Remux sang container khác.
- Re-encode video/audio.
- Chuyển subtitle/thumbnail.
- Cắt theo thời gian.
- Nhúng metadata, thumbnail, subtitle và chapter.

### Chỉ định vị trí FFmpeg

```powershell
yt-dlp --ffmpeg-location "D:\Tools\ffmpeg\bin" "URL"
```

Nếu FFmpeg đã có trong `PATH` hoặc đặt cùng `yt-dlp.exe`, thường không cần tùy chọn này.

### Remux video

```powershell
yt-dlp --remux-video mp4 "URL"
```

Remux đổi container mà không mã hóa lại luồng. Nhanh và hầu như không giảm chất lượng, nhưng chỉ thành công nếu codec tương thích với container đích.

### Recode video

```powershell
yt-dlp --recode-video mp4 "URL"
```

Recode cho phép đổi sang định dạng đích ngay cả khi codec nguồn không tương thích, nhưng rất tốn CPU, mất thời gian và có thể giảm chất lượng.

### Giữ file trung gian

```powershell
yt-dlp --keep-video -x --audio-format mp3 "URL"
```

Giữ file video nguồn sau khi trích xuất audio. Hữu ích để debug nhưng tăng dung lượng ổ đĩa.

### Chạy FFmpeg với tham số nâng cao

```powershell
yt-dlp --postprocessor-args "ffmpeg:-hide_banner" "URL"
```

`--postprocessor-args` là tính năng nâng cao. Truyền sai vị trí tham số có thể làm hỏng bước ghép/chuyển đổi; ứng dụng production chỉ nên cung cấp các preset đã kiểm thử thay vì cho người dùng nhập chuỗi tùy ý.

### Chạy lệnh sau khi xử lý

`--exec` cho phép chạy chương trình tại các giai đoạn nhất định. Đây là tính năng mạnh nhưng có rủi ro command injection. Nếu xây dựng ứng dụng desktop:

- Không ghép dữ liệu URL/tiêu đề do người dùng nhập vào shell command.
- Không cho người dùng từ xa truyền trực tiếp `--exec`.
- Gọi executable với mảng arguments, không xây chuỗi shell.

---

## 19. Metadata, thumbnail, chapter nhúng trong file

### Nhúng metadata

```powershell
yt-dlp --embed-metadata "URL"
```

Có thể ghi tiêu đề, nghệ sĩ/uploader, ngày, mô tả và dữ liệu khác tùy container và extractor.

### Nhúng thumbnail làm ảnh bìa

```powershell
yt-dlp --embed-thumbnail "URL"
```

Phù hợp với file nhạc hoặc media library. Một số container cần thumbnail được chuyển đổi trước.

### Nhúng subtitle và chapter

```powershell
yt-dlp --write-subs --embed-subs --embed-chapters "URL"
```

### Chỉnh metadata bằng regex

- `--parse-metadata`: lấy dữ liệu từ trường này để tạo/cập nhật trường khác.
- `--replace-in-metadata`: tìm và thay thế nội dung trong metadata bằng regex.

Đây là chức năng nâng cao, hữu ích khi chuẩn hóa album, artist, series hoặc tên tập. Hãy thử trước với `--simulate --print` vì regex sai có thể đổi hàng loạt metadata.

### Nối video của playlist

```powershell
yt-dlp --concat-playlist always "URL_PLAYLIST"
```

Chỉ nên nối các mục có format/codec phù hợp và khi mục tiêu thật sự cần một file duy nhất. Với playlist lớn, việc nối làm tăng thời gian xử lý, dung lượng tạm và khó khôi phục khi lỗi.

---

## 20. SponsorBlock

SponsorBlock dùng dữ liệu cộng đồng để đánh dấu hoặc loại bỏ các đoạn như sponsor, intro, outro, self-promotion trên video YouTube.

### Đánh dấu đoạn thành chapter

```powershell
yt-dlp --sponsorblock-mark "sponsor,intro,outro" "URL"
```

Video không bị cắt; các đoạn được thêm thành chapter để trình phát nhận biết.

### Loại bỏ đoạn

```powershell
yt-dlp --sponsorblock-remove "sponsor" "URL"
```

Việc cắt có thể không hoàn toàn chính xác do keyframe. Dữ liệu SponsorBlock cũng không phải lúc nào cũng có hoặc chính xác.

### Tắt SponsorBlock

```powershell
yt-dlp --no-sponsorblock "URL"
```

---

## 21. Chế độ xem thông tin, JSON và kiểm thử

### Mô phỏng, không tải file media

```powershell
yt-dlp --simulate "URL"
```

### In tiêu đề, ID và thời lượng

```powershell
yt-dlp --print "%(title)s | %(id)s | %(duration_string)s" "URL"
```

### Xuất một JSON cho mỗi video

```powershell
yt-dlp --dump-json "URL"
```

Với playlist, kết quả có thể là nhiều dòng JSON. Ứng dụng nên đọc theo JSON Lines thay vì giả định toàn bộ stdout là một object duy nhất.

### Xuất một JSON tổng

```powershell
yt-dlp --dump-single-json "URL_PLAYLIST"
```

Tùy chọn này thuận tiện để lấy cấu trúc playlist nhưng có thể tạo output rất lớn.

### Chỉ lấy URL media trực tiếp

```powershell
yt-dlp -g "URL"
```

URL trực tiếp thường có thời hạn, có thể gắn với IP/header/cookie và không nên lưu lâu dài hoặc xem là link công khai ổn định.

### Hiện tên file dự kiến

```powershell
yt-dlp --print filename -o "%(title)s [%(id)s].%(ext)s" "URL"
```

### Log chi tiết để chẩn đoán

```powershell
yt-dlp -v "URL"
```

Khi báo lỗi cho dự án, thông thường nên cập nhật và lấy verbose log:

```powershell
yt-dlp -Uv "URL"
```

Trước khi chia sẻ log, kiểm tra và che cookie, token, header, đường dẫn cá nhân hoặc dữ liệu nhạy cảm.

### Theo dõi tiến trình có cấu trúc

```powershell
yt-dlp --newline --progress-template "download:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s" "URL"
```

`--newline` giúp mỗi lần cập nhật tiến độ nằm trên một dòng, dễ đọc từ ứng dụng. Với tích hợp nghiêm túc, nên kiểm thử kỹ schema output theo phiên bản hoặc dùng API Python/hooks thay vì phân tích chuỗi hiển thị cho con người.

---

## 22. Cấu hình mặc định bằng `yt-dlp.conf`

File cấu hình cho phép lưu các tùy chọn dùng thường xuyên mà không phải gõ lại.

Ví dụ cấu hình Windows:

```text
# Thư mục đầu ra
-P "D:\Videos"

# Tên file an toàn, có ID để tránh trùng
-o "%(title)s [%(id)s].%(ext)s"

# Tên phù hợp Windows
--windows-filenames
--trim-filenames 180

# Không tải cả playlist khi URL là một video
--no-playlist

# Có retry hợp lý
--retries 10
--fragment-retries 10
```

Một vị trí cấu hình thường dùng trên Windows:

```text
%APPDATA%\yt-dlp\config.txt
```

Với bản portable, có thể đặt `yt-dlp.conf` cạnh `yt-dlp.exe`.

### Bỏ qua cấu hình trong một lần chạy

```powershell
yt-dlp --ignore-config "URL"
```

Tùy chọn này đặc biệt hữu ích khi debug vì giúp biết lỗi đến từ lệnh hiện tại hay file cấu hình cũ.

### Không nên đặt mặc định toàn cục

- Cookie hoặc mật khẩu.
- `--no-check-certificates`.
- `--force-overwrites` nếu dữ liệu quan trọng.
- `--exec` với lệnh tùy ý.
- Số fragment song song quá cao.
- Recode mọi video vì sẽ tốn tài nguyên không cần thiết.

---

## 23. Tích hợp `yt-dlp` vào ứng dụng desktop

### Nguyên tắc kiến trúc

Ứng dụng nên có một lớp adapter riêng cho `yt-dlp`, ví dụ:

```text
UI
  -> Download service
      -> yt-dlp adapter
          -> process runner
              -> yt-dlp executable
```

Adapter chịu trách nhiệm:

- Kiểm tra executable và phiên bản.
- Chuẩn hóa URL đầu vào.
- Xây mảng arguments từ các lựa chọn đã cho phép.
- Khởi chạy tiến trình không qua shell.
- Đọc stdout/stderr liên tục.
- Parse metadata và tiến độ.
- Cho phép hủy job.
- Áp timeout hợp lý.
- Ghi log đã loại dữ liệu nhạy cảm.
- Trả về mã lỗi có cấu trúc cho UI.

### Không tạo command bằng nối chuỗi

Không nên:

```ts
exec(`yt-dlp ${userInput}`);
```

Nên dùng API nhận executable và mảng arguments, ví dụ Node.js:

```ts
import { spawn } from "node:child_process";

const child = spawn(ytDlpPath, [
  "--no-playlist",
  "--dump-single-json",
  url,
], {
  shell: false,
  windowsHide: true,
});
```

`shell: false` và mảng arguments giúp giảm nguy cơ command injection. Vẫn phải validate URL, kiểm soát tùy chọn và không cho người dùng chèn option nguy hiểm.

### Lấy metadata trước khi tải

```powershell
yt-dlp --no-playlist --dump-single-json --skip-download "URL"
```

Ứng dụng có thể hiển thị:

- Tiêu đề.
- Thumbnail.
- Thời lượng.
- Kênh.
- Danh sách format.
- Có/không có phụ đề.

Sau đó người dùng mới bấm tải hoặc bắt đầu thuyết minh.

### Tách thư mục làm việc theo job

Mỗi job nên có thư mục riêng:

```text
jobs/<job-id>/
  input/
  temp/
  transcript/
  tts/
  output/
  logs/
```

Không dùng trực tiếp tiêu đề video làm định danh job vì có thể trùng, quá dài hoặc chứa ký tự đặc biệt.

### Đặt output có ID ổn định

```powershell
yt-dlp -P "JOB_INPUT" -o "source-%(id)s.%(ext)s" "URL"
```

Ứng dụng dễ tìm file hơn so với phụ thuộc hoàn toàn vào tiêu đề.

### Cơ chế hủy

Khi người dùng bấm Hủy:

1. Gửi tín hiệu dừng cho process tree.
2. Chờ tiến trình kết thúc trong thời gian ngắn.
3. Nếu không dừng, mới buộc kết thúc process tree.
4. Đánh dấu job là `cancelled`, không phải `failed`.
5. Xóa file tạm theo chính sách của ứng dụng hoặc cho phép resume.

Trên Windows, cần đảm bảo FFmpeg/aria2c là tiến trình con cũng được dừng, nếu không chúng có thể tiếp tục chạy nền.

### Mã lỗi gợi ý cho UI

| Mã nội bộ | Ý nghĩa hiển thị |
|---|---|
| `YTDLP_NOT_FOUND` | Không tìm thấy `yt-dlp` |
| `FFMPEG_NOT_FOUND` | Thiếu FFmpeg cho bước ghép/chuyển đổi |
| `UNSUPPORTED_OR_CHANGED_SITE` | Website chưa hỗ trợ hoặc vừa thay đổi |
| `AUTH_REQUIRED` | Nội dung cần đăng nhập/quyền truy cập |
| `BOT_CHECK_REQUIRED` | Nền tảng yêu cầu xác minh người dùng |
| `FORMAT_UNAVAILABLE` | Chất lượng/định dạng đã chọn không tồn tại |
| `NETWORK_TIMEOUT` | Kết nối quá thời gian |
| `RATE_LIMITED` | Bị giới hạn số request |
| `DISK_FULL` | Không đủ dung lượng |
| `FILE_PERMISSION_DENIED` | Không có quyền ghi file |
| `DOWNLOAD_CANCELLED` | Người dùng đã hủy |
| `POSTPROCESS_FAILED` | Tải xong nhưng FFmpeg/hậu xử lý lỗi |

Không nên chỉ hiện nguyên stderr dài cho người dùng phổ thông. Hãy hiện thông báo dễ hiểu và cho phép mở phần “Chi tiết kỹ thuật”.

### Quản lý phiên bản

- Ghi nhận phiên bản `yt-dlp` và FFmpeg trong trang Cài đặt/Chẩn đoán.
- Kiểm tra cập nhật theo yêu cầu người dùng hoặc theo lịch hợp lý.
- Không cập nhật executable giữa lúc đang có job chạy.
- Có checksum/chữ ký hoặc tải từ nguồn phát hành tin cậy.
- Với ứng dụng đóng gói, kiểm tra giấy phép của mọi dependency được phân phối kèm.

### Các option không nên cho nhập tự do từ UI

- `--exec`.
- `--postprocessor-args`.
- `--downloader-args`.
- `--config-locations`.
- `--plugin-dirs`.
- `--paths`/`--output` chưa được kiểm soát.
- Header/cookie dạng raw.

Nên chuyển các lựa chọn UI thành preset an toàn do ứng dụng định nghĩa.

---

## 24. Các lệnh mẫu thực tế

Thay `URL` và đường dẫn bằng giá trị thật.

### 1. Tải một video tốt nhất

```powershell
yt-dlp --no-playlist "URL"
```

### 2. Tải MP4 tối đa 1080p

```powershell
yt-dlp --no-playlist -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 "URL"
```

### 3. Tải MP4 có tính tương thích cao

```powershell
yt-dlp --no-playlist -t mp4 "URL"
```

### 4. Chỉ tải audio nguồn tốt nhất

```powershell
yt-dlp --no-playlist -f "ba" "URL"
```

### 5. Chuyển thành MP3 192 Kbps

```powershell
yt-dlp --no-playlist -x --audio-format mp3 --audio-quality 192K "URL"
```

### 6. Chỉ tải phụ đề tiếng Việt và tiếng Anh

```powershell
yt-dlp --no-playlist --write-subs --write-auto-subs --sub-langs "vi,en" --convert-subs srt --skip-download "URL"
```

### 7. Tải video kèm phụ đề và thumbnail

```powershell
yt-dlp --no-playlist --write-subs --sub-langs "vi,en" --embed-subs --write-thumbnail --embed-thumbnail --embed-metadata "URL"
```

### 8. Tải playlist và không tải lại video cũ

```powershell
yt-dlp --yes-playlist --download-archive archive.txt -o "%(playlist_title)s\%(playlist_index)03d - %(title)s [%(id)s].%(ext)s" "URL_PLAYLIST"
```

### 9. Tải đoạn 30 giây đến 2 phút

```powershell
yt-dlp --no-playlist --download-sections "*00:00:30-00:02:00" "URL"
```

### 10. Lấy metadata cho ứng dụng mà không tải

```powershell
yt-dlp --no-playlist --dump-single-json --skip-download "URL"
```

### 11. Lấy metadata nhanh của playlist

```powershell
yt-dlp --flat-playlist --dump-single-json "URL_PLAYLIST"
```

### 12. Tải vào thư mục tạm rồi chuyển sang thư mục đích

```powershell
yt-dlp -P "temp:D:\VideoTool\Temp" -P "home:D:\VideoTool\Downloads" -o "%(title)s [%(id)s].%(ext)s" "URL"
```

### 13. Tải có cookie từ Chrome khi thật sự cần

```powershell
yt-dlp --cookies-from-browser chrome --no-playlist "URL"
```

### 14. Tải playlist chậm hơn để hạn chế rate-limit

```powershell
yt-dlp -t sleep -N 2 --download-archive archive.txt "URL_PLAYLIST"
```

### 15. Lệnh phù hợp làm đầu vào cho pipeline thuyết minh

```powershell
yt-dlp --no-playlist -f "bv*+ba/b" --merge-output-format mkv -P "temp:JOB_TEMP" -P "home:JOB_INPUT" -o "source-%(id)s.%(ext)s" "URL"
```

MKV là container linh hoạt cho file nguồn trung gian. Bước xuất cuối cùng có thể chuyển sang MP4 H.264/AAC nếu cần khả năng tương thích rộng.

---

## 25. Lỗi thường gặp và cách xử lý

### `'yt-dlp' is not recognized...`

Nguyên nhân: Windows không tìm thấy executable.

Cách xử lý:

1. Kiểm tra `yt-dlp.exe` có tồn tại.
2. Đặt nó trong thư mục của ứng dụng hoặc thư mục đã thêm vào `PATH`.
3. Mở PowerShell mới sau khi sửa `PATH`.
4. Chạy `yt-dlp --version`.

### `ffmpeg not found`

Nguyên nhân: cần ghép/chuyển đổi nhưng không tìm thấy FFmpeg.

Cách xử lý:

- Đặt `ffmpeg.exe` và `ffprobe.exe` trong `PATH`, cạnh `yt-dlp.exe`, hoặc chỉ đường dẫn bằng `--ffmpeg-location`.
- Chạy `ffmpeg -version` để kiểm tra.

### `Requested format is not available`

Nguyên nhân: bộ lọc `-f` không khớp định dạng của video.

Cách xử lý:

```powershell
yt-dlp -F "URL"
```

Sau đó chọn ID/bộ lọc tồn tại hoặc thêm phương án dự phòng bằng `/`.

### `HTTP Error 403`

Nguyên nhân có thể gồm:

- URL media tạm đã hết hạn.
- Website yêu cầu header/cookie/PO Token phù hợp.
- IP hoặc tài khoản bị giới hạn.
- Phiên bản `yt-dlp` quá cũ.
- Thiếu JavaScript runtime/challenge solver với YouTube hiện tại.

Thứ tự xử lý an toàn:

1. Chạy lại bằng URL trang gốc, không dùng URL media cũ.
2. Cập nhật `yt-dlp`.
3. Đọc toàn bộ warning từ `-v`.
4. Kiểm tra JavaScript runtime theo hướng dẫn chính thức.
5. Chỉ dùng cookie nếu nội dung thật sự yêu cầu quyền tài khoản.
6. Nếu thông báo nói đến PO Token, xem wiki chính thức đang cập nhật.

### `Sign in to confirm you're not a bot`

Đây là kiểm tra của nền tảng, không phải lỗi chuyển mã.

- Không lặp request liên tục.
- Thử lại sau một khoảng thời gian.
- Cập nhật `yt-dlp`.
- Khi hợp lệ và cần thiết, để người dùng xác minh trong trình duyệt rồi dùng cookie của chính họ.
- Không thiết kế cách vượt CAPTCHA/DRM.

### `HTTP Error 429: Too Many Requests`

Nguyên nhân: gửi quá nhiều request trong thời gian ngắn.

Cách xử lý:

- Dừng và chờ.
- Giảm `-N`.
- Thêm `-t sleep` hoặc các tùy chọn sleep.
- Không retry vô hạn.
- Không đổi IP/proxy hàng loạt để né giới hạn của dịch vụ.

### File tải xong nhưng không mở được

Kiểm tra:

- Bước ghép FFmpeg có thất bại không.
- Codec có được thiết bị hỗ trợ không.
- File `.part` có bị đổi tên nhầm thành file hoàn chỉnh không.
- Dung lượng ổ đĩa có hết giữa chừng không.

Dùng preset MP4 tương thích hoặc chuyển mã đầu ra cuối bằng FFmpeg khi cần.

### Tên file quá dài hoặc không hợp lệ

```powershell
yt-dlp --windows-filenames --trim-filenames 160 -o "%(title)s [%(id)s].%(ext)s" "URL"
```

### Cookie không đọc được từ Chrome/Edge

Nguyên nhân có thể là trình duyệt khóa database cookie, thay đổi cơ chế mã hóa hoặc sai profile.

- Đóng hoàn toàn trình duyệt rồi thử lại nếu phù hợp.
- Chỉ định đúng browser/profile theo cú pháp của `--help`.
- Không chạy ứng dụng với quyền Administrator nếu không cần.
- Không yêu cầu người dùng tải cookie lên server.

### Chỉ thấy một số format hoặc cảnh báo JavaScript runtime

YouTube hiện có thể cần runtime JavaScript/challenge-solving để lấy đủ format. `yt-dlp` hỗ trợ các runtime như Deno, Node, QuickJS hoặc Bun tùy phiên bản; bản hiện tại ưu tiên Deno và executable chính thức có thể kèm thành phần cần thiết. Hãy làm theo cảnh báo chính xác của `yt-dlp -v` và wiki EJS chính thức thay vì dùng lệnh cũ trên mạng.

### Debug sạch cấu hình

```powershell
yt-dlp --ignore-config -Uv "URL"
```

Lệnh này loại ảnh hưởng của file cấu hình và in log chi tiết của bản đã cập nhật.

---

## 26. Giới hạn, an toàn và bản quyền

### Quyền sử dụng nội dung

Chỉ tải và xử lý nội dung khi:

- Bạn là chủ sở hữu.
- Nội dung có giấy phép cho phép tải/chỉnh sửa.
- Chủ sở hữu đã cho phép.
- Nền tảng cung cấp tính năng hoặc điều khoản phù hợp với mục đích đó.
- Việc sử dụng phù hợp pháp luật áp dụng cho bạn.

### `yt-dlp` không phá DRM

Không xây dựng tính năng vượt DRM, CAPTCHA hoặc cơ chế kiểm soát truy cập. Có URL xem được trong trình duyệt không tự động đồng nghĩa với quyền tải, tái phân phối hoặc tạo bản thuyết minh.

### Các dữ liệu cần xem là bí mật

- Cookie trình duyệt.
- Authorization header.
- Token truy cập.
- URL media có chữ ký.
- File `.netrc`.
- Log verbose có thông tin phiên.

### An toàn khi tích hợp vào ứng dụng

- Validate URL và chỉ chấp nhận `http:`/`https:` nếu sản phẩm không cần scheme khác.
- Dùng allowlist các option được UI hỗ trợ.
- Không chạy qua shell.
- Giới hạn thời gian, dung lượng, số video playlist và số job đồng thời.
- Kiểm tra dung lượng trống trước khi tải và trước khi FFmpeg xử lý.
- Cô lập thư mục của từng job.
- Không tin tên file/metadata do website trả về.
- Làm sạch log trước khi người dùng xuất báo cáo.
- Cập nhật dependency từ nguồn tin cậy.
- Xóa dữ liệu tạm theo chính sách rõ ràng.

---

## 27. Bảng tra cứu nhanh

| Mục đích | Tùy chọn chính |
|---|---|
| Xem phiên bản | `--version` |
| Cập nhật executable | `-U` |
| Xem trợ giúp đầy đủ | `--help` |
| Tải URL | `yt-dlp "URL"` |
| Không tải playlist | `--no-playlist` |
| Xem format | `-F` |
| Chọn format | `-f` |
| Sắp xếp/ưu tiên format | `-S` |
| Ghép container đầu ra | `--merge-output-format` |
| Remux | `--remux-video` |
| Re-encode | `--recode-video` |
| Chỉ lấy audio | `-x` |
| Chọn định dạng audio | `--audio-format` |
| Chọn chất lượng audio | `--audio-quality` |
| Xem subtitle | `--list-subs` |
| Tải subtitle thủ công | `--write-subs` |
| Tải subtitle tự động | `--write-auto-subs` |
| Chọn ngôn ngữ subtitle | `--sub-langs` |
| Chuyển subtitle | `--convert-subs` |
| Nhúng subtitle | `--embed-subs` |
| Tải thumbnail | `--write-thumbnail` |
| Nhúng thumbnail | `--embed-thumbnail` |
| Lưu JSON | `--write-info-json` |
| Xuất JSON ra stdout | `--dump-json`, `--dump-single-json` |
| Không tải media | `--skip-download`, `--simulate` |
| Chọn thư mục | `-P` |
| Đặt tên file | `-o` |
| Tên phù hợp Windows | `--windows-filenames` |
| Giới hạn tên | `--trim-filenames` |
| Tải URL từ file | `-a` |
| Không tải lại mục cũ | `--download-archive` |
| Chọn phần tử playlist | `--playlist-items` |
| Lọc video | `--match-filters` |
| Cắt theo thời gian/chapter | `--download-sections` |
| Tách chapter | `--split-chapters` |
| Nhúng chapter | `--embed-chapters` |
| Fragment song song | `-N` |
| Giới hạn tốc độ | `-r`, `--limit-rate` |
| Retry | `-R`, `--retries` |
| Nghỉ giữa request/video | `--sleep-requests`, `--sleep-interval` |
| Dùng proxy | `--proxy` |
| Cookie từ browser | `--cookies-from-browser` |
| Cookie từ file | `--cookies` |
| Log chi tiết | `-v` |
| Bỏ qua config | `--ignore-config` |
| Chỉ định FFmpeg | `--ffmpeg-location` |
| Đánh dấu SponsorBlock | `--sponsorblock-mark` |
| Xóa đoạn SponsorBlock | `--sponsorblock-remove` |

---

## Nguồn tham khảo chính thức

- [Kho mã nguồn và tài liệu sử dụng chính thức của yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FAQ chính thức](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
- [Hướng dẫn extractor và lưu ý YouTube](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)
- [YouTube PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [Danh sách website/extractor được hỗ trợ](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

> Vì `yt-dlp` và các website thay đổi liên tục, khi một lệnh không còn hoạt động, hãy ưu tiên kết quả của `yt-dlp --help`, `yt-dlp -Uv "URL"` và wiki chính thức ở thời điểm gặp lỗi.
