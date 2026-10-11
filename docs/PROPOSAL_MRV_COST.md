# PROPOSAL_MRV_COST — Đánh đổi kiến trúc MRV lúa giá rẻ cho nông hộ đại trà

Ngày: 2026-10-05. Người đặt bài: anh Văn.
Mục tiêu duy nhất: **tự động hoá MRV với chi phí thấp nhất, đại trà nông dân áp dụng được,
trên nền hệ thống điều khiển qua mạng (NCS)**. "Digital twin" chỉ là nhãn theo thời đại,
không phải mục tiêu. Bỏ qua các ghi chú màu vàng trong PDF tiền bối.

Nguồn phong cách: bài tiền bối `Toward Zero-Touch Smart Agriculture` (10 trang IEEE 2 cột,
6 contributions đánh số, có bảng "Summary of Headline Results", mục Limitations riêng,
số liệu cụ thể kèm caveat trung thực — ví dụ "5.4% gain, high-variance, we report transparently").

---

## 1. TRẦN KINH TẾ (mọi phương án phải lọt qua cửa này)

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| Tín chỉ cấp được theo VM0051 mới | **4–6 tín chỉ/ha** (CDM cũ 12–15 đã bị huỷ 4,5 triệu) | RMI Technical Explainer 2025 (think tank, KHÔNG peer-review) |
| Giá tín chỉ methane lúa, giao dịch thật 2026 | **$15–25/tCO₂e**; Ấn Độ offtake $17–18; JCM Indonesia $25 | upstream.ag + Quantum Commodity Intelligence, 01–03/2026 |
| **Doanh thu/ha/vụ (5 tín chỉ × $15–25)** | **$75–125 ≈ 1,9–3,1 triệu VND** | tính từ 2 dòng trên |

⚠️ **SỬA LỖI 2026-10-05:** bản đầu dùng giá $8/tín chỉ lấy từ tài liệu Gemini anh Văn gửi
(không phải nguồn tra được). Tra lại thị trường 2026: $15–25/t. Mọi % doanh thu bên dưới
đã tính lại theo $75/ha (cận dưới bảo thủ).
| Cơ cấu chi phí MRV | monitoring **77%**, reporting 13,6%, verification 9,4% | J. Environ. Manage. 2026 (sciencedirect S0301479726003452) |
| Audit bên thứ ba | ~€1.250/dự án + 4h/nông trại (trung gian) + 2h/nông dân | cùng nguồn |
| Mật độ mẫu | 4 ha/mẫu (mô hình) vs 1,2 ha/mẫu (đo trực tiếp) | cùng nguồn |
| Chi phí sản xuất 1 vụ | 28–35 triệu VND/ha | báo Sóc Trăng 2026 |

**Ngưỡng chết:** MRV mà ngốn >~50% doanh thu (tức >~$37/ha theo cận dưới $75) thì nông hộ bỏ cuộc.
Bài toán thật: monitoring = 77% chi phí → **đánh vào monitoring là đánh đúng chỗ đau**.

## 2. BỐN KIẾN TRÚC — CHI PHÍ ƯỚC TÍNH ($/ha/vụ)

⚠️ Giá hardware là **ƯỚC TÍNH của em** (neo theo giá thị trường IoT VN), cần báo giá thật
trước khi đưa vào bất kỳ hồ sơ nào. Các neo khác có nguồn ở mục 1.

| Kiến trúc | Hardware | Kết nối | Lao động | Audit | **Tổng** | % doanh thu |
|---|---|---|---|---|---|---|
| A) Ống quan trắc thủ công + ảnh chụp (QĐ 4801 hiện tại) | 0,50 | 0 | 8,00 | 4 | **12,50** | 17% |
| B) IoT cảm biến mực nước mỗi thửa (RYNAN-style) | 11,25 | 2,00 | 1,50 | 4 | **18,75** | 25% |
| C) Viễn thám (Sentinel-1/2, ALOS-2) + kiểm chứng thực địa | 0 | 0 | 2,00 | 6 | **8,00** | 11% |
| D) **MRV từ lệnh điều khiển (NCS gate)** | 3,60 | 1,50 | 0,30 | 3 | **8,40** | **11% — và chi phí biên của MRV ≈ 0** |

(% doanh thu tính theo cận dưới $75/ha. **SỬA 2026-10-05:** bản đầu kết luận "B LOẠI vì
ăn 47% doanh thu" — kết luận đó dựa trên giá $8 SAI. Với giá 2026 thật ($15–25/t), B chỉ
ăn 15–25% doanh thu, tức **vẫn sống được về kinh tế**. Xem lại phán quyết ở mục 3bis.)

Giả định D: 1 gateway (~$120, Raspberry Pi-class) + van/bơm điều khiển phục vụ ~6–7 ha
(đúng quy mô thí nghiệm HTX 6 thửa đã có trong `multifield_raw.csv`), khấu hao 5 vụ.

### 3bis. Phán quyết sau khi sửa giá — trung thực lại từ đầu

Với giá tín chỉ thật 2026 ($15–25/t), **không kiến trúc nào chết vì chi phí tuyệt đối nữa**
(A 17%, B 25%, C 11%, D 11% doanh thu cận dưới). Vậy D thắng vì cái gì? Không phải vì B
"chết giá" như bản đầu nói sai, mà vì 3 lý do định tính có bằng chứng:

1. **Chi phí biên của MRV trong D ≈ 0** — gateway được nông dân/HTX trả tiền vì lợi ích
   tưới (−20% nước, −công), bằng chứng MRV là phế phẩm. Trong B, cảm biến mua CHỈ để đo
   MRV → toàn bộ $18,75/ha là chi phí phải biện minh bằng riêng doanh thu tín chỉ.
   Khi giá tín chỉ sụt (thị trường VCM từng sập 99,9% năm 2024 — RMI), B vỡ trước tiên.
2. **Độ phân giải thời gian**: B và D đều theo giờ; C (vệ tinh 2–4 ngày) không thấy pha
   khô 72h giữa kỳ → C chỉ là cross-check, không thay được bằng chứng bậc 1.
3. **Bằng chứng định lý**: chỉ D có cơ chế im lặng + ngưỡng σ* + audit trail kèm lý do —
   đúng thứ tự ưu tiên bằng chứng QĐ 4801 và nguyên tắc bảo thủ VM0051 §9.3.

Kết luận sửa: **D vẫn là phương án đề xuất, nhưng lập luận phải là "chi phí biên ≈ 0 +
bằng chứng bậc 1 theo giờ", KHÔNG phải "B quá đắt".** Giá hardware $45/node vẫn là ước
tính của em, chưa có báo giá — nếu báo giá thật thấp hơn nhiều (node mực nước nội địa
<200k VND) thì B càng cạnh tranh hơn nữa; D khi đó thắng thuần ở mục 1 và 3.

### Vì sao D thắng về BẢN CHẤT chứ không chỉ về số
**Chi phí biên của MRV trong D gần bằng 0**: gateway được mua để TỰ ĐỘNG HOÁ TƯỚI
(tiết kiệm nước 20%+, tiết kiệm công — thứ nông dân tự trả tiền vì lợi ích trực tiếp),
còn bằng chứng MRV là **phế phẩm miễn phí** của chính việc vận hành đó (audit trail:
lệnh, thời điểm, độ sâu, delivered/withheld + lý do, theo giờ).
Trong A/B/C, MRV là chức năng phải trả tiền riêng. Trong D, MRV đi ké.

## 3. ĐỐI CHIẾU PHÁP LÝ (đã verify từ NOTES_MRV.md, đọc toàn văn VM0051 v1.1 + QĐ 4801)

1. **Thứ tự ưu tiên bằng chứng QĐ 4801**: "hồ sơ tưới tiêu & rút nước THỰC TẾ" > kế hoạch
   > lịch trình > ghi chú thực địa > tuyên bố. Audit trail của gate = **bậc 1**, độ phân giải giờ,
   thay cho ảnh chụp thủ công mà quy trình đang yêu cầu.
2. **Quy tắc AWD 3 ngày** (QĐ 4801 dòng 399–400): rút nước chỉ hiệu quả nếu không tưới lại
   trong ≥3 ngày → mã hoá được thành ràng buộc cứng trong gate (đã làm: chỉ số `awd_effective`
   đếm pha khô ≥72h; sinh ra ngưỡng f_σ ≤ 0,025).
3. **Bộ máy bất định**: I7 (coverage 95%, z=1,96) dùng ĐÚNG công thức Phụ lục A12 QĐ 4801.
4. **VM0051 §9.3**: nguyên tắc bảo thủ — σ bảo thủ của gate (over-cover 0,99–1,00) trùng hướng.
5. **VM0051 Appendix 4**: khuyến nghị DMRV; viễn thám revisit 2–4 ngày KHÔNG thấy được
   pha khô 72h giữa kỳ → C một mình là không đủ độ phân giải thời gian, chỉ dùng làm
   **cross-check giảm tần suất VVB xuống ruộng** (audit $6 → $3/ha trong mô hình).
6. **KHÔNG được claim**: hệ này không lượng hoá CH₄/N₂O (cần EF của IAE), không thay
   thẩm định bên thứ ba. Claim đúng: *"command-gating layer whose audit trail supplies
   MRV-grade activity data for the water-management practice"*.

## 4. GÌ TỪ BÀI TIỀN BỐI — GIỮ / BỎ

| Ý tưởng Zero-Touch SGA | Quyết định | Lý do |
|---|---|---|
| UAV + path planning information-gain | **BỎ** | UAV không cần khi bằng chứng sinh từ van/bơm; chi phí vận hành cao, đúng chỗ anh nói "không thực tế" |
| Federated learning đa UAV | **BỎ** | FL giải bài privacy + non-IID giữa các UAV — ta không có fleet; thêm FL là thêm chi phí không mua thêm bằng chứng nào |
| Semantic communication (giảm 48,5% payload) | **BỎ** (giữ làm future work 1 dòng) | Payload của gate là ~vài chục byte/lệnh/ngày qua LoRa — không có bài toán nén |
| DRL adaptive sensor activation | **BỎ** | Quyết định 1 lần/ngày, tập lệnh 3–4 mức — DRL là dao mổ trâu giết gà, lại không chứng minh được an toàn; gate chance-constrained có ĐỊNH LÝ |
| Digital Twin "predictive orchestration" | **GIỮ — chính là FAO-56 twin đang có** | Twin nhận lệnh u làm đầu vào (what-if) đã verify; chạy trên gateway $35 không cần GPU. Nhãn DT hợp pháp, không phải marketing |
| Three-tier CS/Edge/MSS | **GIỮ dạng rút gọn** | HTX gateway (edge) + cloud tỉnh/doanh nghiệp (CS) + van (MSS) — khớp hạ tầng đề án 1 triệu ha |
| Zero-touch framing | **GIỮ làm câu chuyện** | "Không chạm": nông dân không phải đi đo, không phải chụp ảnh, không phải khai báo — bằng chứng tự sinh |

## 5. PHƯƠNG ÁN ĐỀ XUẤT: **"Điều khiển tức giám sát" (Control-as-Monitoring)**

```
[Mây: Sentinel-1/2 miễn phí — cross-check vùng, giảm VVB]
        ⇅ (4G, vài KB/ngày)
[Gateway HTX: FAO-56 twin + safety gate + audit trail — $35–120, chạy offline được]
        ⇅ (LoRa, mất gói là BÌNH THƯỜNG — T2/π xử lý)
[Van/bơm + cảm biến mực nước tối thiểu 1 cái/HTX để tái neo]
        ⇅
[Ruộng: pha khô ≥72h tự động đạt → tín chỉ]
```

Vì sao đây là NCS đúng nghĩa và vì sao NCS LÀ điểm bán:
- Kênh xuống ruộng mất gói là hiện thực (LoRa nông thôn). Mọi kiến trúc "gửi lệnh là tới"
  sẽ tưới đúp → phá pha khô 72h → **mất tín chỉ cả chu kỳ**. TwinGate đã đo: T2 giảm 23%
  nước tưới đúp so gửi lại mù; σ* cho biết khi nào phải IM LẶNG — im lặng có nhật ký,
  và nhật ký đó vẫn là bằng chứng MRV ("bằng chứng của việc không làm" — thứ ảnh vệ
  tinh 2–4 ngày không tái dựng được).
- Cảm biến tối thiểu (1 node/HTX để tái neo twin, không phải 1 node/thửa) vì hệ quả đã
  chứng minh: f_σ=0,02 thì KHÔNG BAO GIỜ tái neo vẫn làm được AWD (σ tĩnh 3,21mm < 3,57mm).
  Đây là chỗ tiết kiệm hardware sâu nhất mà vẫn có lý thuyết đỡ: **độ chính xác của TWIN
  quan trọng hơn tần suất CẢM BIẾN**.

### Đã có sẵn (không phải làm lại)
- Toàn bộ cơ chế gate + T2 + σ* + 7 bất biến: `src/`, tests pass, 36.480 episodes.
- Thí nghiệm HTX 6 thửa + 3 luật phân bổ ngân sách + điểm chéo 320mm: `multifield_raw.csv`.
- Kịch bản mặn theo triều (cửa sổ AWD trùng mặn tháng 2–4): `tide_salinity.py`.
- Đối chiếu pháp lý đầy đủ: `NOTES_MRV.md`.

### Cần làm thêm (nếu đi tiếp hướng này thành bài/sản phẩm)
1. **Bảng chi phí có báo giá thật** (RYNAN smart water meter, van LoRa, RPi) thay ước tính.
2. Mã hoá **ràng buộc cứng AWD-72h vào gate** (hiện mới là chỉ số đo) — candidate feature.
3. Thí nghiệm **cross-check viễn thám**: dùng chuỗi audit trail làm ground-truth giả lập cho
   Sentinel-1 (độ phân giải 6–12 ngày) → đo "VVB phải xuống ruộng bao nhiêu lần" → con số
   $6→$3/ha thành ĐO chứ không phải ước tính.
4. Xử lý **sụt lún 1,1–2,5 cm/năm** (G4 trong PROBLEM_VN): mốc "15cm dưới mặt ruộng" trôi —
   twin FAO-56 dùng depletion fraction (tương đối theo FC/WP) nên TỰ MIỄN NHIỄM với cao trình
   tuyệt đối → đây là argument bán hàng khoa học rất mạnh, chưa bài nào nói.

## 6. GIỚI HẠN TRUNG THỰC CỦA CHÍNH ĐỀ XUẤT NÀY

- Mọi giá hardware ($45/node, $120 gateway, van LoRa) là **ƯỚC TÍNH của em, chưa có báo
  giá và chưa có nguồn công khai** — bắt buộc thay bằng báo giá thật trước khi dùng.
- Lao động $1/h và phân bổ audit $3–6/ha là ước tính thô; bài JEM 2026 (DOI
  10.1016/j.jenvman.2026.128885, đã verify Crossref) cho €1.250/dự án + 4h/nông trại nhưng
  ở **bối cảnh carbon farming EU**, không phải lúa ĐBSCL — chỉ dùng làm bậc độ lớn.
- Giá tín chỉ $15–25/t là nguồn **ngành** (upstream.ag, Quantum Commodity Intelligence,
  Carbon Pulse 2026), không phải số liệu chính thức; Verra Registry: 8 dự án VM0051,
  ~1,73 triệu tín chỉ/năm (materialsindustry.com 2026).
- Chưa có số đo chi phí MRV thực tế của 11 mô hình thí điểm QĐ 4801 (chưa công bố).
- Gate cần van/bơm điều khiển được — ruộng phụ thuộc cống chung của HTX thì phải có
  thoả thuận thể chế, không thuần kỹ thuật.
- Thẩm định bên thứ ba vẫn bắt buộc; hệ này giảm CHI PHÍ chuẩn bị bằng chứng, không bỏ
  được bước VVB.

## 7. PHONG CÁCH VIẾT HỌC TỪ TIỀN BỐI (cho bài báo tiếp theo)

1. Mở đầu bằng 5 thách thức ĐÁNH SỐ, mỗi cái 1–2 câu, rồi "(i)…(v)" contributions đối xứng.
2. Bảng "Summary of Headline Results" cuối phần experiments — 1 bảng gom mọi số bán được.
3. Số âm/nhỏ vẫn báo cáo kèm giải thích ("5.4% gain, smaller and high-variance, reported
   transparently") — cùng tinh thần với σ bảo thủ và C2 scenario của ta.
4. Limitations + Future Work tách thành mục riêng, đánh số 1) 2) 3).
5. Mật độ: 10 trang IEEE 2 cột ~6.600 từ, 8 bảng, 0 phương án trang trí — bảng gánh số liệu,
   chữ chỉ kể chuyện.
