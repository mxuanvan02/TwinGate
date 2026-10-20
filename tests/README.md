# Cách chạy bộ test của TwinGate

**Chạy bằng Python trực tiếp, KHÔNG dùng `pytest`.**

```bash
cd <repo root>
for f in tests/test_*.py; do python3 "$f" || echo "FAIL: $f"; done
```

Kết quả mong đợi: cả 7 file đều exit 0.

| File | Kiểm tra | Kết quả |
|---|---|---|
| `test_log_filters.py` | 46 phép thử bộ lọc vật lý + neo | `PASS 46 \| FAIL 0` |
| `test_water_balance.py` | cân bằng nước FAO-56 | `ALL CHECKS PASSED` |
| `test_twin_gate.py` | bản sao số + cổng an toàn | `ALL CHECKS PASSED` |
| `test_dmax_proposition.py` | mệnh đề về `d_max` | `ALL d_max PROPOSITION CHECKS PASS` |
| `test_ncs_invariants.py` | bất biến NCS | `ALL INVARIANTS HOLD` |
| `test_tide_salinity.py` | thuỷ triều / mặn | `ALL TIDE/SALINITY TESTS PASS` |
| `test_command_resend.py` | gửi lại lệnh | `ALL CHECKS PASSED` |

## Vì sao không dùng `pytest`

Các file test được viết theo kiểu **script**: chúng tự chạy khi được gọi và kết thúc
bằng `raise SystemExit(main())` hoặc `sys.exit(...)`, tức có lời gọi `sys.exit` ở cấp
module. `pytest` cố **thu thập** (collect) các file này, gặp `SystemExit` trong lúc
import và dừng với lỗi nội bộ (rc=3, không thu thập được test nào) — chứ không phải
bộ test bị hỏng.

Nếu vẫn muốn dùng `pytest`, hãy gọi từng file như một tiến trình con
(`subprocess.run([sys.executable, path])`) thay vì để pytest import chúng.

## Bộ test có fail-closed không?

Có. Mỗi file trả về mã thoát khác 0 khi có phép thử sai (`sys.exit(1)` / `return 1`),
nên không có chuyện "in FAIL mà vẫn exit 0". Đây là điểm đã được kiểm tra độc lập
trong đợt rà soát trước khi nộp (2026-10-15).
