#!/usr/bin/env python3
"""Sinh bang LaTeX TIENG VIET cho ban HUJOS-TT tieng Viet (main_hujos_vi.tex).

NGUYEN TAC BAT BUOC (giong make_tables_hujos.py): KHONG chep lai 400 dong sinh so.
Script nay doc CAC FILE BANG DA SINH tu outputs/*.csv (ban tieng Anh), roi:
  (1) dich nhan/ten bang qua mot BANG TRA CUONG CHE — o chu nao khong nam trong
      bang tra thi AssertionError, khong duoc dich doan;
  (2) doi dinh dang so sang kieu Viet Nam (dau phay thap phan, dau cham phan nghin);
  (3) assert SO DONG, SO VACH va TAP CHU SO cua hai ban trung nhau — tuc ban tieng
      Viet khong the lech so lieu voi ban tieng Anh.

Vi sao khong dich truc tiep trong make_tables_anchored.py: nhan nam rac khap 9 ham,
them nhanh ngon ngu o do se tao hai duong code sinh so — dung thu ma
make_tables_hujos.py sinh ra de tranh. Doc bang EN da sinh la cach duy nhat bao dam
mot nguon so.

QUY UOC SO KIEU VIET NAM (academic-prose: "Vietnamese uses the decimal comma"):
  3.23        -> 3,23
  2,153       -> 2.153          (dau phay nghin cua EN thanh dau cham)
  0.60--0.85  -> 0,60--0,85
  \textbf{49.0} -> \textbf{49,0}
So nguyen va phan tram khong co phan thap phan thi giu nguyen.

BAI HOC (2026-10-08, 3 loi da tra gia trong chinh script nay):
  * Lop ky tu "o thuan so" ban dau thieu dau '/' nen o "0/60" bi xep nham thanh o
    CHU -> AssertionError gia. Phan loai o phai lay theo NOI DUNG that cua bang.
  * digits_of() tra ve LIST; "".join(digits_of(c) for c in cells) noi list voi nhau
    -> TypeError. phai "".join("".join(...) for ...).
  * O hon hop "\textbf{5\%} accused" va "0/60 (honest)" khong thuoc loai nao tron
    ven: phai boc \textbf{} de quy, va phai TRU cac cum tieng Anh da dich (SUBPHRASES)
    ra truoc khi kiem "con chu tieng Anh khong".

Chay:
    python3 experiments/make_tables_hujos.py       # sinh bang EN truoc
    python3 experiments/make_table_benchmark.py    # sinh tab_benchmark EN
    python3 experiments/make_tables_hujos_vi.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper2_hujos" / "tables"
DEST = ROOT / "paper2_hujos" / "tables_vi"

# 4 bang than bai + 5 bang phu luc (S1-S6 cua ban tieng Anh).
TABLES = [
    # than bai
    "tab_false_accusation", "tab_credit", "tab_defence", "tab_benchmark",
    # phu luc
    "tab_threat", "tab_umax", "tab_f2_unreachable", "tab_baseline", "tab_setup",
]

# ---------------------------------------------------------------------------
# BANG TRA NHAN — CUONG CHE. Moi o CHU cua bang EN phai co mat o day.
# ---------------------------------------------------------------------------
LABELS = {
    # --- nhan dung chung ---
    "true": "đúng",
    "FALSE": "SAI",
    "varies": "thay đổi",
    "accused": "bị oan",
    # --- tab_false_accusation ---
    "Defence layer": "Lớp phòng thủ",
    "Honest, paper conditions": "Trung thực, điều kiện giấy",
    "Honest, field conditions": "Trung thực, điều kiện ruộng",
    "v1 tier 0 (physics, point model)": "v1 tầng 0 (vật lý, mô hình điểm)",
    "v1 tier 1 (absolute $G>5$\\,mm)": "v1 tầng 1 (tuyệt đối $G>5$\\,mm)",
    "v2 tier 0 ($\\forall$ over $\\Theta$)": "v2 tầng 0 ($\\forall$ trên $\\Theta$)",
    "v2 tier 1 ($\\tau(n)$ scales with events)": "v2 tầng 1 ($\\tau(n)$ co giãn theo số lệnh)",
    "Device-anchored command log": "Bản ghi lệnh neo theo thiết bị",
    # --- tab_credit ---
    "Log type": "Loại nhật ký",
    "Altered logs": "Nhật ký bị sửa",
    "Paired dry phases (before $\\to$ after)": "Pha khô ghép cặp (trước $\\to$ sau)",
    "Inflation": "Thổi phồng",
    "$t$": "$t$",
    "no altered log": "không sửa nhật ký",
    "reference": "mốc",
    # --- tab_defence ---
    "Fraud variant": "Biến thể gian lận",
    "Escapes v1": "Lọt v1",
    "Escapes v2 physics": "Lọt v2 vật lý",
    "Caught by anchor": "Neo thiết bị bắt",
    "All genuinely forged": "Mọi nhật ký thật sự giả",
    # --- ten bien the (dung chung ca 3 bang) ---
    "Honest farmer (field conditions)": "Nông dân trung thực (điều kiện ruộng)",
    "Added irrigation events": "Thêm lệnh tưới",
    "Infeasible claimed depth": "Độ sâu khai không khả thi",
    "Omission of real commands": "Bỏ sót lệnh thật",
    "Claim consolidation, 24 h": "Gộp khai báo, 24 h",
    "Claim consolidation, 96 h": "Gộp khai báo, 96 h",
    "Time shifting (rational)": "Dịch thời điểm (duy lý)",
    "Rational adversary": "Đối thủ duy lý",
    # --- tab_benchmark ---
    "Verification route": "Phương án xác minh",
    "Confirmable dry phases ($n=150$)": "Pha khô xác nhận được ($n=150$)",
    "Observations per season": "Số lần quan sát mỗi vụ",
    "Devices per plot": "Thiết bị mỗi thửa",
    "Photo + self-report (current practice)": "Ảnh + tự khai (thực hành hiện hành)",
    "Sentinel-1A+1B (6-day revisit)": "Sentinel-1A+1B (chu kỳ 6 ngày)",
    "Sentinel-1A alone (12-day revisit)": "Sentinel-1A đơn lẻ (chu kỳ 12 ngày)",
    "Continuous water-level tube (IoT)": "Ống đo mực nước liên tục (IoT)",
    "Signed command record (this work)": "Bản ghi lệnh có chữ ký (bài này)",
    "0 (PVC tube)": "0 (ống PVC)",
    "1 per plot": "1 mỗi thửa",
    "0 (controller)": "0 (bộ điều khiển)",
    # --- tab_threat ---
    "Total mm": "Tổng mm",
    "Each depth": "Từng độ sâu",
    "Timing": "Thời điểm",
    "What it forges": "Làm giả cái gì",
    "Reference: seven reality-gap axes active":
        "Mốc: bảy trục khác biệt thực tế đang bật",
    "Inflates the record of management activity":
        "Thổi phồng hồ sơ hoạt động quản lý",
    "One third of entries set to the whole storage span":
        "Một phần ba số mục đặt bằng toàn bộ dung tích chứa",
    "Deletes a 96 h window to manufacture a dry phase":
        "Xoá cửa sổ 96 h để tạo ra một pha khô",
    "Same water, fewer and larger events":
        "Cùng lượng nước, ít lần tưới hơn và lớn hơn",
    "Same water, events snapped to a coarse grid":
        "Cùng lượng nước, các lần tưới bám vào lưới thô",
    "Hill-climbs each hour to maximise creditable dry phases":
        "Leo đồi theo từng giờ để tối đa số pha khô được cấp tín chỉ",
    "Chooses the consolidation window that maximises dry phases":
        "Chọn cửa sổ gộp làm tối đa số pha khô",
    # --- tab_umax ---
    "Soil (FAO-56 Table 2)": "Loại đất (FAO-56 Bảng 2)",
    "Span (mm)": "Biên độ (mm)",
    "$u_{\\max}$ at $w_0=0$": "$u_{\\max}$ tại $w_0=0$",
    "$u_{\\max}$ at $w_0=0.90$": "$u_{\\max}$ tại $w_0=0{,}90$",
    "sandy loam": "đất thịt pha cát",
    "loam": "đất thịt",
    "silt loam": "đất thịt pha limon",
    "silty clay loam": "đất thịt pha sét limon",
    "clay": "đất sét",
    "Range to be published": "Dải phải công bố",
    # --- tab_f2_unreachable ---
    "Station": "Trạm",
    "Year": "Năm",
    "Max clipped depletion": "Cạn kiệt cắt ngọn lớn nhất",
    "$V_2$ fires": "$V_2$ kích hoạt",
    "Interpretation": "Diễn giải",
    "never below wilting point": "không bao giờ xuống dưới điểm héo",
    "reachable": "có thể đạt",
    "can tho": "Cần Thơ",
    "soc trang": "Sóc Trăng",
    "ca mau": "Cà Mau",
    # --- tab_baseline ---
    "Architecture": "Kiến trúc",
    "Hardware": "Phần cứng",
    "Connectivity": "Kết nối",
    "Labour": "Nhân công",
    "Audit": "Thẩm định",
    "Total \\$/ha": "Tổng \\$/ha",
    "Note": "Ghi chú",
    "Manual observation tube plus photographs": "Ống quan trắc thủ công kèm ảnh chụp",
    "Water-level sensor per plot": "Cảm biến mực nước mỗi thửa",
    "Remote sensing plus field verification": "Viễn thám kèm kiểm tra thực địa",
    "Attested log, this work": "Nhật ký được chứng thực, bài này",
    "current practice under Decision 4801": "thực hành hiện hành theo Quyết định 4801",
    "accurate, hard to scale to smallholders":
        "chính xác, khó mở rộng cho nông hộ nhỏ",
    "revisit 2 to 4 days": "chu kỳ chụp 2 đến 4 ngày",
    "gateway timestamp is what makes it admissible":
        "dấu thời gian của gateway là thứ làm nó được chấp nhận",
    # --- tab_setup ---
    "Component": "Thành phần",
    "Value": "Giá trị",
    "Weather": "Thời tiết",
    "Hourly ERA5 via the Open-Meteo archive, no missing values":
        "ERA5 theo giờ qua kho lưu trữ Open-Meteo, không có giá trị thiếu",
    "Stations": "Trạm",
    # o DONG sinh tu CSV (danh sach tram sap xep). Neu CSV doi -> gate FAIL va
    # phai them o moi vao day, khong duoc de script tu doan.
    "3: ca mau, can tho, soc trang": "3: Cà Mau, Cần Thơ, Sóc Trăng",
    "Climate years": "Năm khí hậu",
    "2024, 2025 (2024 water-scarce, 2025 water-surplus)":
        "2024, 2025 (2024 khan nước, 2025 thừa nước)",
    "(2024 water-scarce, 2025 water-surplus)":
        "(2024 khan nước, 2025 thừa nước)",
    "Window": "Cửa sổ",
    # THANG viet BANG CHU ("tháng Ba"/"tháng Năm") chu khong viet "tháng 3"/
    # "tháng 5": gate bat tap CHU SO cua hai ban phai trung nhau, va ban dich
    # khong duoc phep SINH THEM so. LOI THAT da bat (2026-10-08):
    #   EN=1292160 vs VI=132952160  <- "tháng 3"/"tháng 5" them chu so 3 va 5.
    # Day la bang chung gate nay co tac dung: no chan ca loi dich vo tinh doi so.
    "1 March to 29 May (2\\,160 h), the delta dry season":
        "từ ngày 1 tháng Ba đến ngày 29 tháng Năm (2\\,160 h), mùa khô đồng bằng",
    "Soil textures sampled": "Loại đất được lấy mẫu",
    "5 across the FAO-56 Table 2 range": "5 loại trải theo FAO-56 Bảng 2",
    "Reality-gap axes": "Trục khác biệt thực tế",
    "7: soil, $K_c$ stage, $\\eta$, field rain, seepage, recording behaviour, $w_0$":
        "7: đất, giai đoạn $K_c$, $\\eta$, mưa tại ruộng, thấm bờ, hành vi ghi chép, $w_0$",
    "Irrigation efficiency $\\eta$": "Hiệu suất tưới $\\eta$",
    "0.60--0.85 (water reaching roots / water pumped)":
        "0,60--0,85 (nước tới rễ / nước bơm)",
    "$K_c$ regimes": "Chế độ $K_c$",
    "fixed 1.05 (as published) and staged 1.05/1.20/0.90":
        "cố định 1,05 (như đã công bố) và theo giai đoạn 1,05/1,20/0,90",
    "Recording noise": "Nhiễu ghi chép",
    # o DONG dai: ca o la mot chuoi tieng Anh, phai dich nguyen cum (khong the
    # dua vao duong "o so hon" vi co qua nhieu tu >= 4 chu cai).
    "forget 5\\%, round to 5\\,mm, one-day delay 35\\%, depth error 15\\% within $\\pm$35\\%":
        "quên 5\\%, làm tròn đến 5\\,mm, trễ một ngày 35\\%, sai độ sâu 15\\% "
        "trong $\\pm$35\\%",
    "Fraud variants": "Biến thể gian lận",
    "Uncertainty set $|\\Theta|$": "Tập bất định $|\\Theta|$",
    "Initial states $|w_0|$": "Trạng thái đầu $|w_0|$",
    "Replays per log": "Số lần phát lại mỗi nhật ký",
    "Logs audited": "Số nhật ký được kiểm",
    "three naive, four adversarial": "ba ngây thơ, bốn đối kháng",
}

# O hon hop: cum tieng Anh ngan nam TRONG o co so. Thay theo thu tu, roi doi so.
SUBPHRASES = [
    (" (reference)", " (mốc)"),
    ("(reference)", "(mốc)"),
    (" (honest)", " (trung thực)"),
    ("(honest)", "(trung thực)"),
    (" accused", " bị oan"),
    ("no altered log", "không sửa nhật ký"),
    ("(three naive, four adversarial)", "(ba ngây thơ, bốn đối kháng)"),
    ("forget 5\\%, round to 5\\,mm, one-day delay 35\\%, depth error 15\\% within $\\pm$35\\%",
     "quên 5\\%, làm tròn đến 5\\,mm, trễ một ngày 35\\%, sai độ sâu 15\\% trong $\\pm$35\\%"),
    ("30 = 5 soils $\\times$ 2 $K_c$ regimes $\\times$ 3 efficiencies",
     "30 = 5 loại đất $\\times$ 2 chế độ $K_c$ $\\times$ 3 hiệu suất"),
    ("5, spanning depletion 0 to 0.90", "5, trải cạn kiệt từ 0 đến 0,90"),
    ("24 (reduced $\\Theta$) and 150 (full $\\Theta$)",
     "24 ($\\Theta$ rút gọn) và 150 ($\\Theta$ đầy đủ)"),
]

KEEP_AS_IS = {"---", "$t$", "n/a"}

# Ten rieng / thuong hieu / thuat nguyen dang PHAI giu nguyen (rigid designator,
# academic-prose). Token tach theo '-': "Open-Meteo" -> "Open", "Meteo".
ALLOW_EN = {"ERA5", "Open", "Meteo", "Sentinel", "gateway", "IoT", "PVC",
            "FAO", "VM0051", "v1", "v2", "tier", "A", "B"}

# O "thuan so" = co chu so, va sau khi bo lenh LaTeX + bo cac cum SUBPHRASES thi
# khong con tu tieng Anh dai >= 4 chu cai, khong co ky tu non-ASCII.
HAS_LETTER_RUN = re.compile(r"[A-Za-z]{4,}")
NUMERIC_CHARS = re.compile(r"^[-+0-9.,/():;\s\\%{}$^_~\[\]=<>|a-zA-Z]*$")


def to_vn_numbers(s: str) -> str:
    """Doi dinh dang so kieu Anh -> kieu Viet Nam trong mot o da dich xong chu.

    LOI DA SUA (2026-10-09, peer review F3): thu tu cu doi dau phay nghin
    TRUOC (2,153 -> 2.153) roi doi dau cham thap phan SAU (2.153 -> 2,153) —
    hai buoc hoa nhau, ket qua '2,153' quay ve dung chu no bat dau. Bang 4 ban
    VI in '2,153' ma nguoi Viet doc la 'hai phay mot nam ba'.
    CACH SUA: dua dau cham thap phan ve ky tu trung gian (sentinel) TRUOC,
    xu ly dau phay nghin, roi moi tra sentinel ve dau phay.
    """
    SENT = "\x00"
    out = s
    # 1) dau cham thap phan -> sentinel: 3.23 -> 3\x0023
    out = re.sub(r"(?<=\d)\.(?=\d)", SENT, out)
    # 2) dau phay nghin kieu EN -> dau cham: 2,153 -> 2.153
    out = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", ".", out)
    # 3) sentinel -> dau phay thap phan kieu Viet: 3\x0023 -> 3,23
    return out.replace(SENT, ",")


def digits_of(s: str) -> str:
    return "".join(re.findall(r"\d", s))


def split_cells(line: str) -> list[str]:
    """Tach mot dong bang theo ' & ' — KHONG tach trong {} de khong vo \\textbf{a & b}."""
    cells, depth, cur = [], 0, []
    for ch in line:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "&" and depth == 0:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    return cells


def _residual_english(c: str) -> str:
    """Bo cac cum SUBPHRASES da biet va lenh LaTeX, de xem con tieng Anh khong.

    LOI DA SUA (2026-10-08): ban dau ham nay bo `\\command` TRUOC khi replace
    SUBPHRASES. Hau qua: o dai `30 = 5 soils $\\times$ 2 $K_c$ regimes ...` bi
    bien thanh `30 = 5 soils   2 $K_c$ regimes ...` (mat `\\times`), nen khong con
    khop voi key SUBPHRASES (van giu `\\times`) -> replace that bai -> residual con
    `soils/regimes/efficiencies` -> bi xep nham la o CHU chua dich va AssertionError.
    Thu tu DUNG: replace SUBPHRASES (khop nguyen van, con `\\command`) TRUOC, roi
    moi bo `\\command` sau.
    """
    resid = c
    for en, _ in SUBPHRASES:
        resid = resid.replace(en.strip(), " ")
    resid = re.sub(r"\\[a-zA-Z]+", " ", resid)
    return resid


def translate_cell(cell: str, tbl: str, lineno: int) -> str:
    """Dich mot o. O chu PHAI co trong LABELS; o so chi doi dinh dang."""
    c = cell.strip()

    # 1) \textbf{X}Y  ->  \textbf{dich X} + dich Y  (de quy)
    m = re.match(r"\\textbf\{(.+?)\}(.*)$", c, re.S)
    if m:
        out = "\\textbf{" + translate_cell(m.group(1), tbl, lineno) + "}"
        tail = m.group(2).strip()
        if tail:
            out += " " + translate_cell(tail, tbl, lineno)
        return out

    if c in KEEP_AS_IS:
        return c

    # 2) tach ~\cite{...}
    cite = ""
    m = re.fullmatch(r"(.*?)~\\cite\{([^}]*)\}", c, re.S)
    if m:
        c, cite = m.group(1).strip(), "~\\cite{" + m.group(2) + "}"

    # 3) nhan trong bang tra (chinh xac)
    if c in LABELS:
        return LABELS[c] + cite

    # 4) nhan co chua so (vd "Confirmable dry phases ($n=150$)"):
    #    so sanh sau khi che so, va giu so that cua ban EN.
    stripped = re.sub(r"\d+", "N", c)
    for k, v in LABELS.items():
        if re.sub(r"\d+", "N", k) == stripped:
            out = v
            for n in re.findall(r"\d+", c):
                out = re.sub(r"\d+", n, out, count=1)
            return out + cite

    # 5) o so / o so hon: dich cum con roi doi dinh dang so
    has_digit = bool(re.search(r"\d", c))
    ascii_only = not re.search(r"[^\x00-\x7f]", c)
    no_english = not HAS_LETTER_RUN.search(_residual_english(c))
    if has_digit and ascii_only and no_english and NUMERIC_CHARS.match(c):
        out = c
        for en, vi in SUBPHRASES:
            out = out.replace(en, vi)
        return to_vn_numbers(out) + cite

    raise AssertionError(
        f"{tbl}.tex dong {lineno}: o CHU khong co trong bang tra LABELS: {c!r}\n"
        f"  -> Them nhan tieng Viet vao LABELS hoac SUBPHRASES trong "
        f"experiments/make_tables_hujos_vi.py. KHONG duoc dich doan bo qua.")


def convert(name: str) -> None:
    src = SRC / f"{name}.tex"
    if not src.exists():
        raise SystemExit(f"thieu {src.relative_to(ROOT)}: chay make_tables_hujos.py "
                         f"va make_table_benchmark.py truoc")
    en = src.read_text(encoding="utf-8")
    out_lines, n_rows, mismatches = [], 0, []
    keep_prefix = ("\\begin{tabular}", "\\end{tabular}", "\\fittocol",
                   "\\toprule", "\\midrule", "\\bottomrule")
    for ln, line in enumerate(en.split("\n"), 1):
        st = line.rstrip()
        if (not st) or st.startswith("%") or st == "}" or st.startswith(keep_prefix):
            out_lines.append(line)
            continue
        body = st[:-2].rstrip() if st.endswith("\\\\") else st
        tail = st[len(body):]
        cells = split_cells(body)
        vi = [translate_cell(c, name, ln) for c in cells]
        if len(cells) != len(vi):
            mismatches.append((ln, "so o khop"))
        # XAC NHAN: tap chu so cua hai ban giong het nhau
        d_en = "".join(digits_of(c) for c in cells)
        d_vi = "".join(digits_of(c) for c in vi)
        if d_en != d_vi:
            mismatches.append((ln, f"chu so lech: EN={d_en} VI={d_vi}"))
        n_rows += 1
        out_lines.append(" & ".join(vi) + tail)
    if mismatches:
        for ln, why in mismatches:
            print(f"  !! {name}.tex dong {ln}: {why}")
        raise SystemExit(f"{name}: SO LIEU LECH giua ban EN va ban VI — KHONG xuat")

    DEST.mkdir(parents=True, exist_ok=True)
    NL_ = chr(10)
    hdr = (f"% Sinh TU DONG tu tables/{name}.tex (ban tieng Anh, von sinh tu "
           f"outputs/*.csv){NL_}"
           f"% boi experiments/make_tables_hujos_vi.py. KHONG sua tay.{NL_}"
           f"% Nhan dich qua bang tra cuong che; so chi doi dinh dang sang kieu "
           f"Viet Nam (dau phay thap phan).{NL_}"
           f"% Da assert: cung so dong, cung so vach, cung tap chu so voi ban EN."
           f"{NL_}{NL_}")
    (DEST / f"{name}.tex").write_text(hdr + NL_.join(out_lines), encoding="utf-8")
    print(f"  wrote tables_vi/{name}.tex ({n_rows} dong du lieu, 0 lech so)")


def main() -> int:
    print(f"=== sinh bang tieng Viet tu {SRC.relative_to(ROOT)} ===")
    for t in TABLES:
        convert(t)
    print("=== GATE: cau truc 2 ban phai trung nhau ===")
    for t in TABLES:
        en = (SRC / f"{t}.tex").read_text(encoding="utf-8")
        vi = (DEST / f"{t}.tex").read_text(encoding="utf-8")
        for kind in ("toprule", "midrule", "bottomrule"):
            a, b = en.count("\\" + kind), vi.count("\\" + kind)
            assert a == b, f"{t}: so \\{kind} lech EN={a} VI={b}"
        assert en.count("\\\\") == vi.count("\\\\"), f"{t}: so dong lech"
        # KHONG con soc tieng Anh trong o, NGOAI allow-list ten rieng/thuong hieu
        # (ERA5, Open-Meteo, Sentinel, gateway, IoT, PVC, FAO, VM0051) — nhung tu
        # nay phai giu nguyen theo academic-prose (rigid designator).
        #
        # LOI DA SUA (2026-10-08): ban dau gate nay quet moi tu ASCII >= 4 chu cai,
        # nen bao nham hang loat TIENG VIET: "trung", "gian", "theo", "gian"...
        # deu la chuoi ASCII tron. Cach phan biet dung: mot o DA dich sang tieng
        # Viet thi chac chan chua dau thanh (non-ASCII); o thuan ASCII ma co tu
        # dai >= 4 chu moi la nghi van tieng Anh. O chi chua so/ky hieu thi bo qua.
        for ln, line in enumerate(vi.split("\n"), 1):
            if line.strip().startswith("%") or "tabular" in line:
                continue
            for cell in split_cells(line.rstrip().removesuffix("\\\\")):
                if re.search(r"[^\x00-\x7f]", cell):
                    continue          # co dau tieng Viet -> da dich
                body = re.sub(r"\\[a-zA-Z]+", " ", cell)
                body = re.sub(r"\$[^$]*\$", " ", body)
                words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", body)
                bad = [w for w in words if w not in ALLOW_EN
                       and HAS_LETTER_RUN.match(w)]
                if bad:
                    raise AssertionError(
                        f"{t}.tex VI dong {ln}: con tieng Anh {bad} trong {cell!r}")
        print(f"  PASS {t}: {en.count(chr(92)*2)} dong, 0 soc tieng Anh ngoai allow-list")
    print(f"\nXuat ra: {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
