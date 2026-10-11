# UPGRADE_FINDINGS — 7 lỗ hổng thiết kế và kết quả nâng cấp

Ngày: 2026-10-06. Trạng thái: **đã đo, đã vá, đã test 46/46 PASS**.
Nguồn số liệu: `outputs/eval_theta_reduced_10seeds.csv` (281 nhật ký),
`outputs/eval_theta_full_3seeds.csv` (85 nhật ký), `outputs/reality_gap_probe.csv`.

---

## Vì sao phải làm việc này

Bài báo 2 công bố **"0 bắt oan / 100% phát hiện"**. Con số đó **đúng nhưng vô
nghĩa**, vì quỹ đạo "thật" trong thí nghiệm được sinh ra bằng **đúng mô hình mà
bộ lọc dùng để chấm**: cùng `SoilProfile()` mặc định, cùng forcing ERA5 không
nhiễu, tưới là xung 1 giờ đúng {20,40}mm, ngưỡng đúng 0.80, nông dân ghi đúng
giờ đúng số. Đó là mô hình tự kiểm tra chính nó.

Anh Văn yêu cầu: *phải ứng dụng được thực tế, mô phỏng được tất cả trường hợp
có thể xảy ra, không chỉ con số trên giấy*. Tài liệu này là kết quả.

---

## 7 lỗ hổng, tất cả đều đo được

### #1 — V2 là code chết
`depletion_fraction()` kết thúc bằng `min(1.0, max(0.0, ...))` → clip về [0,1].
Ngưỡng `DEPL_IMPOSSIBLE = 1.02` nên **không bao giờ đúng**.

- Đo: V2 fire **0 lần / 281 nhật ký**.
- Hệ quả: bài báo quảng cáo "ba bộ lọc V1, V2, V4" nhưng chỉ có hai. Đây cũng
  là lý do `tab_intensity` chỉ có cột |V₁| và |V₄|.
- Vá: thêm `depletion_raw()` không clip + F2 fire khi khô hơn điểm héo ≥24h liên
  tiếp. Unit test chứng minh fire được (f2=10).
- **Nhưng phải công bố thêm**: trên ERA5 thật, depletion clip max = **0.998**
  (2024) và **0.988** (2025) tại Cần Thơ → ruộng lúa mùa khô ĐBSCL **không bao
  giờ xuống dưới điểm héo**. V2 sau khi sửa vẫn **0 lần fire end-to-end**. Nó là
  bộ lọc an toàn, KHÔNG phải bằng chứng phát hiện gian lận.

### #2 — Kc cố định 1.05
FAO-56 Table 12 cho lúa là 1.05 (đầu) / 1.20 (giữa) / 0.90 (cuối). Code dùng
1.05 cho mọi giờ → sai ETc **±14,3%**, tích lũy 90 ngày.

### #3 — Một profile đất cho cả 3 tỉnh
span thật dao động **55→90mm** giữa cát pha thịt và sét. Ngưỡng
`u_max = d*·span + ε` phụ thuộc span nên **61mm chỉ đúng cho một loại đất**.

- Vá: `u_max = max(d*, w0)·span + ε`, và công bố **dải [49,0 ; 86,0]mm** trên
  Θ = 5 đất × 2 chế độ Kc × 3 mức η × 5 trạng thái đầu vụ.
- Em đã viết sai công thức này ở bản vá đầu (`(d* − w0)·span + ε`, cho 43,5mm —
  không tương ứng trạng thái vật lý nào). Test đơn vị bắt được.

### #4 — Tầng 1 bắt oan 26,7% nông dân trung thực ← nghiêm trọng nhất về mặt cam kết
Ngưỡng gap **tuyệt đối 5mm**. Nông dân thật quên ghi 5%, làm tròn 5mm, ghi trễ
1 ngày → `U(L) < M` một cách vô tội.

- Đo: v1 **26,7%** bắt oan (gap max 75mm); v2 **5,0%** (3/60).
- Vá: `τ(n) = δ_rel·M + z·σ(n)` với `σ(n) ∝ √n`, σ_event gộp ba nguồn nhiễu
  (quên ghi, làm tròn `round/2√3`, sai độ sâu).
- **Cái giá phải công bố**: τ co giãn làm **giảm phát hiện omission từ 80%
  xuống 40%**. Đây là đánh đổi thật giữa bắt oan và bắt gian lận, không được giấu.

### #5 — Bắt oan tăng 0% → 8% khi rời điều kiện giấy
Theo loại đất: silty_clay_loam 22%, sandy_loam 18%, clay 6%, silt_loam/loam 0%.

### #6 — Gian lận DỒN LỆNH (vật lý và đồng hồ bơm đều mù)
Giữ nguyên **tổng mm** (gap đồng hồ = 0), giữ từng lệnh dưới ngưỡng, chỉ gộp
nhiều lệnh rải rác thành ít lệnh tập trung → các pha khô dài ra và không bị cắt
→ **n_dry (số pha khô ≥72h, đại lượng tín chỉ được trả) tăng +52% đến +53%**.

- Vá: thêm **F5 = ràng buộc sức thấm** `u ≤ infil·h + ponding` (mặc định
  10mm/h × 1h + 100mm = **110mm**), độc lập với trạng thái bucket. Mặc định lấy
  ở biên nới lỏng nhất để không bắt oan nông dân ghi gộp hai sự kiện liền nhau.
- Đo: F5 fire **648 lần**, nhưng **toàn bộ trên `fraud_infeasible_depth`**.

### #7 — Gian lận DỊCH GIỜ (không đóng được bằng vật lý) ← phát hiện quan trọng nhất
Đây là lý do F5 **không** đóng được #6. Đối thủ không gộp đủ sâu để vượt 110mm;
nó chỉ **dịch giờ** từng lệnh (lệch tới 23h):

- tổng mm không đổi → đồng hồ bơm mù
- từng độ sâu vẫn dưới ngưỡng → F1/F4/F5 mù
- quỹ đạo vẫn tự nhất quán → cân bằng nước không có gì để bắt

**Chỉ có MỘT thứ bị làm giả: THỜI ĐIỂM.**

---

## Kết quả đo (281 nhật ký, Θ rút gọn 10 seeds)

| Loại gian lận | n_dry | lọt v1 | lọt v2 | anchor bắt |
|---|---|---|---|---|
| Nông dân trung thực (ruộng thật) | 3,23 | — | — | **0/60 bắt oan** |
| Khai thêm sự kiện (ngây thơ) | 4,83 (+49%) | 0% | 0% | 23/23 |
| Khai độ sâu bất khả thi | 4,04 (+25%) | 0% | 0% | 23/23 |
| Giấu lệnh | 4,61 (+43%) | 21,7% | 78,3% | **9/9** |
| Dồn lệnh 24h | 4,91 (+52%) | 39,1% | 91,3% | **23/23** |
| Dồn lệnh 96h | 4,96 (+53%) | 39,1% | 91,3% | **23/23** |
| Đối thủ có lý trí | 5,26 (+63%) | **100%** | **100%** | **6/6** |
| **Dịch giờ** | **5,48 (+69%)** | 39,1% | 91,3% | **9/9** |

Kiểm chứng bằng Θ đầy đủ (150 replay/log, 85 nhật ký): **cùng kết luận**, đối thủ
dịch giờ +78,3% tín chỉ, anchor bắt 3/3.

**Bắt oan trên nông dân trung thực: v1 tầng 1 = 26,7% → v2 = 5,0% → anchor = 0%.**

---

## Kết luận bắt buộc phải sửa trong bài báo

1. **"Tầng 0 thuần app trên điện thoại" KHÔNG đủ tin cậy một mình.** Đối thủ
   dịch giờ thổi phồng **+69% tín chỉ** mà cả vật lý lẫn đồng hồ bơm đều mù.
   Timestamp **phải do gateway đóng dấu** — thứ paper 1 (TwinGate) đã có sẵn, nên
   chi phí biên vẫn ~0 **nếu triển khai kèm paper 1**. Mô hình chi phí phải ghi
   điều kiện này.

2. **Phòng tuyến duy nhất đạt 100%/0% là device-anchored command log**: bắt
   **100%** mọi nhật ký thật sự bị làm giả — đếm lại từ CSV: **28/28** (quick),
   **116/116** (Θ rút gọn 10 seeds), **37/37** (Θ đầy đủ 3 seeds); bắt oan **0/60**
   và **0/18**. Đây mới là đóng góp trung thực của bài — không phải "ba bộ lọc vật
   lý bắt 100%".

3. **Không được nói "ba bộ lọc"**: V2 đã sửa cho fire được nhưng **không kích
   hoạt được trên lúa mùa khô ĐBSCL** (depletion max 0.998). Phải nói V2 là bộ
   lọc an toàn.

4. **Phải công bố đánh đổi của ∀-semantics**: buộc tội kiểu ∀ (chỉ kết tội khi
   mọi θ ∈ Θ đều báo) khôi phục bảo đảm không bắt oan, nhưng làm giảm phát hiện
   omission 80% → 40%.

5. **Mệnh đề u_max yếu hơn bài báo ngụ ý**: đó là chặn **theo từng sự kiện**,
   không theo vụ. Bucket thoát nước liên tục nên cả vụ có thể khai khống nhiều
   lệnh nhỏ sát ngưỡng. Dải đúng là **[49,0; 86,0]mm**, không phải một số 61mm.

---

## Ba lỗi của chính em trong quá trình làm (ghi lại để không tái phạm)

1. **`int(f1 or f2 or f4)`** — Python trả giá trị truthy cuối (7), không phải
   True. Bảng in ra "560% bắt được". Sửa: `(f1+f2+f4+f5) > 0`.
2. **`not r["v2_t0"]` trên CSV** — giá trị là chuỗi `"0"`, `not "0"` = False vì
   chuỗi khác rỗng luôn truthy → mọi dòng ra escape = 0%, kể cả honest_field.
   Sửa: `int()` tường minh trong `analyze_robust_eval.py`.
3. **So sánh baseline chéo** — `honest_paper` sinh từ một lần `build_truth` riêng,
   nhưng em so với `pump_r`/`rec_r` của ruộng khác → báo "bắt oan 56/60 = 93%"
   cho chính nhật ký trung thực. Sửa: `pump_of`/`rec_of` để mỗi biến thể được
   chấm bằng baseline **của chính nó**.
4. **`robust_audit` giao ∩ chỉ trên các θ ĐÃ fire** — tức "∃θ buộc tội" chứ không
   phải "∀θ buộc tội". Test bắt được (102/150 fire mà vẫn kết tội). Sửa: thế giới
   không fire phải đóng góp **tập rỗng** vào phép giao.
5. **`find_env` trong script splice LaTeX** tìm `\begin{` gần label nhất → với
   `eq:decision` nó thay từ `\begin{cases}`, bỏ lại `\begin{equation}` mồ côi.
6. **Đối thủ thiết kế ngu** — bản adversary đầu bơm 343mm khống → n_dry = 0 →
   0 tín chỉ, nó tự hủy. "Bắt 100%" trên kẻ thù đó là vô nghĩa. Kẻ thù đúng phải
   tối đa **n_dry**, không tối đa mm.

---

## File

| File | Vai trò |
|---|---|
| `src/log_filters.py` | Bộ lọc v2: Θ, ∀-audit, `depletion_raw`, F5, τ(n), `umax_for` |
| `tests/test_log_filters.py` | 46 test, mỗi test khóa một lỗ hổng |
| `experiments/reality_gap_probe.py` | 7 trục lệch thực tế + adversary |
| `experiments/robust_audit_eval.py` | Đánh giá v1 vs v2, 9 biến thể gian lận, device-anchor |
| `experiments/analyze_robust_eval.py` | Phân tích CSV (dùng `int()` tường minh) |
| `outputs/eval_theta_reduced_10seeds.csv` | 281 nhật ký |
| `outputs/eval_theta_full_3seeds.csv` | 85 nhật ký, Θ đầy đủ 150 replay/log |
