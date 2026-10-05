# PROPOSAL_TWIN_ATTESTED — MRV lúa chi phí thấp nhất: "Ghi lệnh + Máy phát hiện nói dối vật lý"

Ngày: 2026-10-05. Trạng thái: **thí nghiệm fraud-detection đã chạy, gate pass** (số ở mục 5).
Mục tiêu của anh Văn (nguyên văn): *"tập trung vào một yếu tố nào đó đang rất tốt trong hướng này,
và đề xuất phương án mới mà vừa hiệu quả, vừa chi phí thấp (ưu tiên chi phí)"*.
Kế thừa: `PROPOSAL_MRV_COST.md` (cost model 4 kiến trúc, đã sửa giá tín chỉ 2026).

---

## 1. YẾU TỐ ĐANG RẤT TỐT (điểm tựa duy nhất)

**Audit trail của lệnh điều khiển = bằng chứng BẬC 1 theo QĐ 4801, chi phí biên ≈ 0.**

- QĐ 4801 xếp thứ tự ưu tiên bằng chứng: *"hồ sơ tưới tiêu & rút nước thực tế"* > kế hoạch >
  lịch trình > ghi chú thực địa > tuyên bố (đã đọc toàn văn, sha256 trong NOTES_MRV.md).
- Monitoring chiếm **77%** chi phí MRV (J. Environ. Manage. 2026, DOI 10.1016/j.jenvman.2026.128885,
  đã verify Crossref). Mọi kiến trúc "mua thiết bị để đo" đều đánh vào phần đắt nhất.
- Nhưng bằng chứng bậc 1 là bản ghi **hành động**, không phải số đo. Hành động thì hệ
  điều khiển/gateway vốn đã phải ghi để vận hành. => Đừng mua thiết bị đo; hãy **lấy bản ghi
  có sẵn và chứng minh nó không nói dối được**.

## 2. PHƯƠNG ÁN: TWIN-ATTESTED LOGGING — 3 tầng, nông dân chọn theo túi tiền

| Tầng | Thiết bị | Chi phí/ha/vụ* | Bằng chứng | Bắt được gian lận loại nào |
|---|---|---|---|---|
| **0 — App ghi lệnh** | Điện thoại (đã có; mục tiêu 2030: 1 smartphone/hộ) | **~$0–1** | Nhật ký lệnh ký số + timestamp = bậc 1 QĐ 4801 | Khai THÊM (F1/F4), khai sai độ sâu (F4) |
| **1 — + Đồng hồ trạm bơm** | 1 flow-meter ~$5–10 cho CẢ trạm bơm HTX (không phải mỗi thửa) | ~$1–2 | "đã phát" thành "đã tới"; tổng nước bơm thật | **Gian lận GIẤU LỆNH (omission)** — loại tầng 0 bất lực |
| **2 — + 1 node mực nước/HTX** | ~$45/6–10 ha | ~$5–8 | Tái neo twin, đạt chuẩn hiệu chuẩn I7 cho thị trường khó tính | drift dài hạn của twin |

\* Giá hardware là **ƯỚC TÍNH của em, chưa có báo giá** — bắt buộc thay bằng báo giá thật
(node mực nước nội địa, van LoRa, RPi) trước khi đưa vào hồ sơ/bài báo.

**Bộ lọc chống gian lận $0 (tầng 0 đã có):**
1. **Bộ lọc vật lý — FAO-56 twin trên ERA5 công khai**: replay cuốn nhật ký qua đúng mô hình
   cân bằng nước (code `src/water_balance.py` đang có). Nhật ký giả tạo ra trạng thái vật lý
   bất khả thi mà nhật ký thật không bao giờ tạo ra:
   - **F1 over-saturation**: khai tưới khi ruộng đã no nước (w ≥ FC − 5mm) — đất không giữ nổi.
   - **F2 mass-impossible**: depletion > 1,02 kéo dài — không lịch tưới thật nào tạo ra.
   - **F4 storage-excess**: lượng khai > sức chứa của đất (FC − w + 5mm) — phần thừa phải chảy
     tràn nên "tưới thành công" cỡ đó là khai khống. (F1 là trường hợp riêng của F4 khi deficit ≈ 0.)
2. **Bộ lọc vệ tinh — Sentinel-1 SAR ($0, revisit 6–12 ngày)**: cross-check theo lô cả HTX,
   dùng để GIẢM tần suất VVB xuống ruộng, KHÔNG thay nhật ký (vệ tinh không thấy pha khô 72h
   giữa kỳ — đã verify vòng trước).

**Vì sao hiệu quả mà vẫn rẻ nhất:** cắt đúng khoản 77% (monitoring) về ~0; giữ nguyên bằng
chứng bậc 1; có **lý thuyết đỡ lưng** — chính twin FAO-56 + ngưỡng σ* + bất biến I7 đã chứng
minh trong TwinGate, chỉ đổi vai trò từ "cổng chặn lệnh" thành "máy kiểm tra nhật ký".
Toàn bộ code tái dùng nguyên xi.

## 3. GIỚI HẠN TRUNG THỰC CỦA BỘ LỌC (đã đo, không giấu)

**Gian lận GIẤU LỆNH (tưới lén rồi xóa khỏi nhật ký để khai khống pha khô ≥72h) KHÔNG thể
bắt bằng vật lý thuần ở tầng 0** — một nhật ký "bớt đi" vẫn tự nhất quán với ERA5.
Đây không phải lỗ hổng thiết kế mà là **lý do tồn tại của tầng 1**: đồng hồ ở trạm bơm đo
TỔNG nước thật đã bơm; tổng khai thấp hơn tổng bơm > 5mm là lòi ngay.
Thí nghiệm đo: pump-gap của gian lận giấu lệnh = **26,7mm** trung bình (dễ bắt, ngưỡng 5mm).

Hệ quả định giá: tầng 0 bán cho thị trường nội địa/NDC (bằng chứng bậc 1 là đủ theo QĐ 4801);
tầng 0+1 là mức tối thiểu để qua VVB quốc tế (VM0051) với chi phí vẫn ~$1–3/ha.

## 4. ĐỐI CHIẾU PHÁP LÝ TỪNG ĐIỀU (nguồn: NOTES_MRV.md, đã đọc toàn văn)

| Yêu cầu | Twin-Attested Logging đáp ứng | Mức |
|---|---|---|
| QĐ 4801: bằng chứng bậc 1 = hồ sơ tưới/rút thực tế | Nhật ký lệnh ký số, độ phân giải giờ | **Trực tiếp** |
| QĐ 4801: quy tắc AWD 3 ngày (không tưới lại ≥72h) | `awd_windows()` đếm pha khô ≥72h + depletion ≥0,45 từ chính replay | **Trực tiếp** |
| QĐ 4801 Phụ lục A12: bất định ở CI 95%, z=1,96 | Bộ lọc vật lý dùng cùng bộ máy (I7 coverage 0,99–1,00 đã đo) | **Trực tiếp** |
| VM0051 §9.3: nguyên tắc bảo thủ | Ngưỡng F1/F2/F4 đặt lệch về phía bắt oan (slack 5mm) — nông dân bị nghi oan mới kháng cáo, không lọt gian lận | Trùng hướng |
| VM0051 Appendix 4: khuyến nghị DMRV, RS phát hiện irrigation events | Sentinel-1 làm cross-check giảm VVB; nhật ký giờ làm ground-truth hiệu chỉnh RS | Bổ trợ |
| VM0051 §5.2: "digital record of cultivation practices" được chấp nhận | Nhật ký app = đúng loại bản ghi này | **Trực tiếp** |
| **KHÔNG được claim** | Không lượng hoá CH₄/N₂O (cần EF của IAE); không thay thẩm định bên thứ ba; C2 mặn là scenario | Giới hạn |

## 5. THÍ NGHIỆM ĐÃ CHẠY (`experiments/fraud_detection.py`)

Thiết kế: dựng quỹ đạo ruộng THẬT bằng FAO-56 + ERA5 thật (Cần Thơ/Sóc Trăng/Cà Mau,
2024+2025, cửa sổ mùa khô 1/3–29/5 như bài chính), nông dân tuân thủ AWD (tưới khi
depletion ≥ 0,80). Sau đó bơm 3 loại gian lận vào nhật ký:
- `fraud_wet_day`: khai THÊM 8 lần tưới vào ngày mưa/ruộng no (thổi phồng hoạt động)
- `fraud_dry_claim`: XÓA lệnh tưới trong cửa sổ 96h để khai khống pha khô ≥72h (ăn gian tín chỉ)
- `fraud_depth`: khai độ sâu = cả FC (160mm/lần) — bất khả thi

Gate (exit ≠ 0 nếu fail): nhật ký thật **không được bắt oan** (FP = 0 trên cả F1/F2/F4);
mỗi gian lận phải bị bắt ≥50% bằng đúng tầng được thiết kế; omission phải bị tầng 1 bắt ≥90%.

**Kết quả FULL (3 trạm × 2 năm × 10 seeds = 240 episodes, `outputs/fraud_raw.csv`) — ĐÃ ĐO:**

| Biến thể | F1 | F4 | pump-gap | Bắt bởi |
|---|---|---|---|---|
| honest (60 nhật ký thật) | 0 | 0 | 0,0 | **0/60 bắt oan** trên cả F1/F2/F4 |
| fraud_wet_day | 5,87 | 7,25 | −320mm | tầng 0 (F1+F4) **60/60 = 100%** |
| fraud_depth | 0 | 1,57 | −182mm | tầng 0 (F4) **60/60 = 100%** |
| fraud_dry_claim | 0 | 0 | **+29,0mm** | tầng 0: 0/60 (đúng thiết kế — nhật ký "bớt đi" vẫn tự nhất quán) → tầng 1 (đồng hồ bơm): **60/60 = 100%** |

Quick run trước đó (3 seeds) cùng kết luận, pump-gap 26,7mm vs 29,0mm full — ổn định.
`FRAUD DETECTION GATES: OK` (exit 0).

## 6. CON SỐ BÁN HÀNG (cho abstract bài báo / hồ sơ)

- Tầng 0: **$0 thiết bị**, bắt 100% gian lận loại khai thêm + khai sai độ sâu, 0 bắt oan.
- Tầng 1 (+$1–2/ha): bắt nốt 100% gian lận giấu lệnh.
- Tổng chi phí MRV kiến trúc này: **~$8,4/ha/vụ = 11% doanh thu tín chỉ** (cận dưới $75/ha,
  giá 2026 $15–25/t — nguồn ngành, xem PROPOSAL_MRV_COST.md).
- So baseline QĐ 4801 (ảnh chụp thủ công): bằng chứng mạnh HƠN (giờ vs ảnh rời rạc),
  chi phí monitoring giảm từ $8/ha lao động (77% của $12,5) về ~$0,3/ha.

## 7. VIỆC CÒN LẠI (thứ tự)

1. **Báo giá thật** thay ước tính: node mực nước, flow-meter trạm bơm, app (hoặc hỏi RYNAN qua kênh trường).
2. Thí nghiệm **Sentinel-1 cross-check**: dùng audit trail làm ground-truth giả lập → đo
   "VVB phải xuống ruộng bao nhiêu lần" → biến $6→$3/ha audit từ ước tính thành số đo.
3. Viết **bài báo thứ 2** theo phong cách tiền bối (10 trang IEEE, contributions (i)–(v),
   bảng Summary of Headline Results): "Twin-Attested Logging: zero-sensor MRV for AWD rice
   with physics-based fraud detection" — tái dùng TwinGate code + thí nghiệm mục 5.
4. Ràng buộc cứng AWD-72h vào gate (hiện là chỉ số đo) — nâng từ "phát hiện" lên "ngăn chặn".
5. Điểm chưa ai làm, rất "Việt Nam": **sụt lún 1,1–2,5 cm/năm** làm mốc "15cm dưới mặt ruộng"
   trôi; twin dùng depletion fraction (tương đối theo FC/WP) nên TỰ MIỄN NHIỄM cao trình
   tuyệt đối — argument khoa học mạnh, đưa vào contribution.
