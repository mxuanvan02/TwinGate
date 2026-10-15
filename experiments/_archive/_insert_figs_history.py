#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHEN 3 HINH vao bai (VI + EN HUJOS), caption DUOI hinh theo the le.

VI TRI (chon theo mach lap luan, khong chen tuy tien):
  fig1_method    -> cuoi Muc 2 (07_system_model): so do duong di cua du lieu,
                    dung ngay sau khi nguoi doc da thay phuong trinh thung chua
                    va cach phat lai nhat ky.
  fig3_timeshift -> dau Muc 9.2 'Vat ly khong nhin thay tan cong sinh loi'
                    (sau \\label{sec:results-attack}): hinh minh hoa dung ket qua
                    cua muc do.
  fig2_tradeoff  -> truoc Muc 9.3 'Neo thiet bi bit moi lop': hinh tom tat su
                    danh doi ma muc 9.1-9.2 vua trinh bay, dan vao giai phap.

CAPTION KHONG CHUA CHU SO NAO. LY DO (khong phai tuy y):
  gate check_vi_numbers so EN_DIR = paper2/blocks (ban IEEE) voi VI_DIR =
  paper2_hujos/blocks_vi. Ban IEEE KHONG co thu muc figures_vi/ nen khong the
  chen hinh vao do. Neu caption ban VI chua so (ke ca 'FAO-56' -> so 56) ma ban
  paper2/blocks khong co, gate se bao VI THUA so. Lam long gate de chui lot la
  sai (bai hoc da ghi trong skill) -> viet caption khong so.

THE LE HUJOS-TT: hinh <= 7 cm x 14 cm, caption DUOI hinh, so hinh IN DAM.
  preamble.tex da co \\captionsetup[figure]{position=bottom} va labelfont=bf.
  Dung height=6.9cm de bao dam ca hai chieu (fig1 rong nhat: 6.9*2.005=13.84cm).
  Do lai kich thuoc THAT trong PDF sau khi build, khong tinh tren giay.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path("/media/SAS/Van/DeTai2025/TwinGate_K1")
H = ROOT / "paper2_hujos"
VIB = H / "blocks_vi"
ENB = H / "blocks"          # ban EN cua HUJOS (main_hujos.tex input)

def figblock(fname, caption, label):
    return ("\\begin{figure}[!t]\n\\centering\n"
            f"\\includegraphics[height=6.9cm]{{figures_vi/{fname}}}\n"
            f"\\caption{{{caption}}}\\label{{{label}}}\n\\end{{figure}}\n")

CAP = {
 ("vi", "fig1_method_vi.png", "fig:method"):
  "Đường đi của dữ liệu trong phương pháp. Lớp kiểm toán vật lý phát lại nhật ký "
  "khai báo qua bản sao số cân bằng nước rồi đi qua ba bộ lọc; lớp neo thiết bị đối "
  "chiếu cùng nhật ký đó với bản ghi lệnh có chữ ký của gateway. Mũi tên đứt cho thấy "
  "tấn công dịch thời điểm đi qua lớp vật lý mà không bị phát hiện.",
 ("en", "fig1_method_en.png", "fig:method"):
  "Data flow of the method. The physical audit layer replays the claimed log through "
  "the water-balance twin and then through three filters; the device anchor checks the "
  "same log against the signed command record of the gateway. The dashed arrow shows "
  "the time-shifting attack passing through the physical layer undetected.",
 ("vi", "fig3_timeshift_vi.png", "fig:timeshift"):
  "Tấn công dịch thời điểm trên tập ghép cặp: số pha khô được cấp tín chỉ trước và sau "
  "khi dời thời điểm lệnh, còn tổng lượng nước và từng độ sâu được giữ nguyên. Mức tăng "
  "trên tập bất định đầy đủ được ghi ở góc dưới bên phải.",
 ("en", "fig3_timeshift_en.png", "fig:timeshift"):
  "The time-shifting attack on the paired subset: creditable dry phases before and after "
  "moving the command timestamps, with the total volume and every individual depth "
  "preserved. The gain under the full uncertainty set is noted at the lower right.",
 ("vi", "fig2_tradeoff_vi.png", "fig:tradeoff"):
  "Sự đánh đổi giữa hai loại sai sót theo ba tầng phòng thủ. Giảm tỷ lệ kết tội oan nông "
  "dân trung thực thì tăng tỷ lệ lọt lưới tấn công dịch thời điểm; chỉ tầng neo thiết bị "
  "đạt cả hai bằng không.",
 ("en", "fig2_tradeoff_en.png", "fig:tradeoff"):
  "Trade-off between the two error types across the three defence tiers. Lowering the "
  "false-accusation rate raises the escape rate of the time-shifting attack; only the "
  "device anchor reaches zero on both.",
}

# caption phai khong chua chu so (khai bao + kiem tra that)
for (lang, f, lab), cap in CAP.items():
    digits = re.findall(r"\d", cap)
    assert not digits, f"caption {f} chua chu so {digits} -> se lam lech gate"
print(f"  OK: {len(CAP)} caption khong chua chu so nao")

edits = []   # (path, mode, anchor_regex_or_None, text, label)

for lang, d in [("vi", VIB), ("en", ENB)]:
    sfx = "_vi" if lang == "vi" else "_en"
    # 1) fig1: append cuoi file 07_system_model.tex
    edits.append((d / "07_system_model.tex", "append", None,
                  "\n" + figblock(f"fig1_method{sfx}.png",
                                  CAP[(lang, f"fig1_method{sfx}.png", "fig:method")],
                                  "fig:method"),
                  "fig1 " + lang))
    # 2) fig3: chen NGAY SAU \label{sec:results-attack}
    edits.append((d / "05_design_results.tex", "after_regex",
                  r"\\label\{sec:results-attack\}\n",
                  "\n" + figblock(f"fig3_timeshift{sfx}.png",
                                  CAP[(lang, f"fig3_timeshift{sfx}.png", "fig:timeshift")],
                                  "fig:timeshift"),
                  "fig3 " + lang))
    # 3) fig2: chen NGAY TRUOC subsection ve neo thiet bi
    pat = r"\\subsection\{Neo thiết bị" if lang == "vi" else r"\\subsection\{The anchor closes"
    edits.append((d / "05_design_results.tex", "before_regex", pat,
                  figblock(f"fig2_tradeoff{sfx}.png",
                           CAP[(lang, f"fig2_tradeoff{sfx}.png", "fig:tradeoff")],
                           "fig:tradeoff") + "\n",
                  "fig2 " + lang))

print(f"\n=== {len(edits)} cho chen ===")
cache, fails = {}, []
for path, mode, pat, text, label in edits:
    if path not in cache: cache[path] = path.read_text(encoding="utf-8")
    s = cache[path]
    if mode == "append":
        cache[path] = s.rstrip("\n") + "\n\n" + text
        print(f"  OK {label}: append cuoi file")
        continue
    ms = list(re.finditer(pat, s))
    if len(ms) != 1:
        fails.append((label, f"anchor match={len(ms)}")); print(f"  !! {label}: anchor match={len(ms)}"); continue
    if mode == "after_regex":
        e = ms[0].end(); cache[path] = s[:e] + text + s[e:]
    else:
        b = ms[0].start(); cache[path] = s[:b] + text + s[b:]
    print(f"  OK {label}: {mode} tai vi tri {ms[0].start()}")

if fails:
    print(f"\n>>> {len(fails)}/{len(edits)} LOI — dung lai, khong ghi file nao")
    sys.exit(1)

# kiem tra LaTeX + khong dech chuyen so
for path, s in cache.items():
    assert s.count("$") % 2 == 0, f"{path}: $ le"
    assert s.count("\\begin{figure}") == s.count("\\end{figure}"), f"{path}: figure lech"
    assert s.count("\\begin{symbolist}") == s.count("\\end{symbolist}"), f"{path}: symbolist"
    assert s.count("\\begin{equation}") == s.count("\\end{equation}"), f"{path}: equation"
    assert "figures_vi/" in s, f"{path}: thieu includegraphics"
    n = len(re.findall(r"\\includegraphics", s))
    print(f"  {path.name} ({path.parent.name}): {n} includegraphics, begin/end khop")

for path, s in cache.items():
    path.write_text(s, encoding="utf-8")
print(f"\n>>> DA GHI {len(cache)} file")
