# 🏯 Công Ty Tu Tiên — Multi-Agent Crew

**Chủ:** Thiện Phannd (Tông chủ)
**Kiến trúc:** CrewAI + 3 agent Gemini (cloud, free) + 1 agent Ollama (local, free)
**Điều phối:** Hermes (kanban + cron + giám sát)

## Đội hình

| Đệ tử | Vai trò | Model | Nguồn |
|---|---|---|---|
| **DanPhong** | Digital Marketing | Gemini (cloud) | OmniRoute (pool key xoay vòng) |
| **KhiPhong** | Lập trình / Dev | Gemini (cloud) | OmniRoute (pool key xoay vòng) |
| **ChapSuDuong** | Phân tích dữ liệu | Gemini (cloud) | OmniRoute (pool key xoay vòng) |
| **GiamSat** | QA / Review / Giám sát viên | Qwen3 8B | Ollama local (0đ) |

## Luồng làm việc (dây chuyền)

```
Input → [DanPhong] → [ChapSuDuong] → [KhiPhong] → [GiamSat (review/fix)] → Output
                    (marketing)      (data)        (code)      (QA bắt lỗi)
```

- Agent chỉ nói chuyện khi được gọi trong luồng — không tán gẫu tự do
- **GiamSat** (model khác = góc nhìn khác) review sản phẩm của 3 đệ tử cloud, bắt lỗi
- Giới hạn vòng lặp: 3 vòng review-fix tối đa, hết là escalate lên Tông chủ
- Mọi trạng thái ghi vào `PROJECT_STATUS.md`

## Cài đặt

```bash
cd ~/cong-ty-tu-tien
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt
cp .env.example .env   # điền key vào
```

## Chạy

```bash
./.venv/Scripts/python -m src.main "Viết kế hoạch marketing cho game Nghịch Hỏa Tinh Đồ"
```

## Trạng thái

Xem `PROJECT_STATUS.md` để biết tiến độ hiện tại.
