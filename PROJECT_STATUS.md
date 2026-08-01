# PROJECT_STATUS.md — Công Ty Tu Tiên

Cập nhật lần cuối: 2026-08-01

## Tiến độ

- [x] Chốt kiến trúc: CrewAI + 3 Gemini (OmniRoute) + 1 Ollama local
- [x] Cài đặt Ollama 0.32.5 + server localhost:11434
- [x] Tải Qwen3 8B (~5GB) + test inference chạy được
- [x] Tạo venv Python 3.11.15 + cài crewai 1.15.10 + litellm
- [x] Dựng khung project (config YAML, 4 agent, luồng dây chuyền)
- [x] Xử lý lỗi portalocker lock trên Windows (monkeypatch lock_store)
- [x] Nạp key OmniRoute vào .env
- [ ] Nạp pool key Gemini (2 key mới từ Tông chủ) — **chờ Tông chủ cấp key**
- [ ] Test chạy 1 vòng cả đội hình
- [ ] Gắn kanban Hermes để điều phối task dài hạn
- [ ] Gắn cron báo cáo định kỳ

## Blockers

- Không có — chờ 2 API key Gemini mới từ Tông chủ.

## Quyết định đã chốt

1. **CrewAI** thay vì AutoGen — không tán gẫu tự do, task-driven, không đốt token
2. **3 tầng fix lỗi:** tự retry → nhờ agent khác (GiamSat, model khác) → escalate Tông chủ
3. Giới hạn vòng lặp tối đa 3 vòng / task
4. Gemini free qua pool key xoay vòng (rủi ro ToS đã cân nhắc — dùng tk phụ)
5. Ollama Qwen3 8B làm giám sát viên + việc vặt (0đ)
