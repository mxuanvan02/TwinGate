#!/usr/bin/env python3
"""Viet lai 2 abstract: vua tran 250 tu, chua du 5 tu khoa, giu nguyen so da verify.

BA van de phai giai quyet CUNG LUC:
  1. Sau khi sua claim sai ('escapes both tiers' -> 4/9 vs 8/9), abstract EN len
     269 tu va VI len 275 tu, vuot tran 250 ma Author Guidelines dat ra cho CA HAI
     ngon ngu.
  2. Guidelines muc 3: "Keywords need to be present in the abstract". Abstract EN
     mo dau bang "Measurement, reporting and verification" trong khi tu khoa la
     "monitoring, reporting and verification" -> khong khop. MONITORING moi la
     thuat ngu chuan cua linh vuc (va cua chinh QD 4801 ban tieng Viet: "Do dac,
     bao cao, tham dinh"). Sua thanh Monitoring.
  3. Abstract VI lap lai hai lan cum "ket toi oan 26,7%" sau lan va truoc -> cat
     mot lan, du tiet kiem tu.

Cach lam: dung danh sach TRIM theo thu tu, cat dan cho toi khi <= 245 tu (bien an
toan duoi tran 250 vi cach dem cua toa soan co the lech vai tu). ASSERT truoc khi
ghi: so tu, du 5 tu khoa, du moi con so da verify. Khong ghi nua chung.

So da verify tu outputs/eval_theta_*.csv (xem experiments/verify_paper_claims.py):
  paired inflation +33% (n=9, t=5.29) / +38% (full, n=3, t=3.46)
  v1 bat 4/9 altered logs nhung bat oan 26.7% honest (16/60)
  v2 bat oan 0/60 (tier-1 5.0%) nhung bo lot 8/9
  anchor 116/116, 0 oan
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

BS = chr(92)
NL = chr(10)
LIMIT = 245            # bien an toan duoi tran 250

D = Path("/media/SAS/Van/DeTai2025/TwinGate_K1")
H = D / "paper2_hujos"
B = D / "paper2" / "blocks"


def words(t: str) -> list[str]:
    """Dem tu nhu toa soan dem: toan thanh 1 token, bo lenh LaTeX va dau."""
    t = re.sub(r"\$[^$]*\$", " MATH ", t)
    t = re.sub(BS + BS + r"[a-zA-Z]+\*?", " ", t)
    t = re.sub(r"[{}~$&" + BS + BS + r"]", " ", t)
    return [w for w in t.split() if re.search(r"[A-Za-z0-9]", w)]


# ---------------------------------------------------------------- EN
# BAN CAT NGAN (2026-10-09, theo peer review): abstract chi giu 5 con so
# (33%, 26.7%, 5.0%, 281, 116/116); 4/9 va 8/9 day xuong than bai (intro +
# Muc 9.2 van giu nguyen). Bo danh sach gia dinh mo hinh va khoang hieu suat
# 0.60-0.85 — chi tiet do thuoc Muc 8 (thiet ke thuc nghiem).
EN_BASE = r"""Monitoring, reporting and verification (MRV) is the bottleneck keeping emission
  reductions in low-emission rice from becoming tradable carbon credits, and
  monitoring is about three quarters of that cost. Because every credit-eligible
  action under alternate wetting and drying is already an \emph{actuation command},
  a farmer-written irrigation log looks like free evidence of the highest rank under
  Decision 4801/QD-BNNMT. We built that layer on an FAO-56 digital twin, then
  attacked it; the attack is the contribution. Replaying a log under public ERA5
  forcing exposes claimed depths no soil can hold, but an adversary who keeps the
  total volume and every individual depth and merely \emph{shifts commands in time}
  inflates creditable dry phases by $33\%$ in paired comparison. No physical tier
  escapes it usefully: the point model accuses $26.7\%$ of honest farmers, and the
  robust tier that cuts false accusation to $5.0\%$ in turn misses most
  time-shifting attacks. Over $281$ audited logs at three Mekong Delta stations
  and two climate years, matching the log against the gateway's signed,
  time-stamped command record catches $116/116$ forged logs and accuses none.
  Physics-based attestation cannot stand alone; the timestamp must come from
  a device, not the farmer."""

EN_TRIMS = []

EN_KEYWORDS = ["alternate wetting and drying",
               "monitoring, reporting and verification",
               "carbon credit", "low-emission rice", "digital twin"]

# ---------------------------------------------------------------- VI
VI_BASE = r"""Đo đạc, báo cáo, thẩm định (MRV) là nút thắt khiến mức giảm phát thải của lúa phát thải thấp chưa thành tín
chỉ các-bon; giám sát chiếm ba phần tư chi phí. Vì mọi hành động quản lý nước
đủ điều kiện cấp tín chỉ trong tưới khô ướt luân phiên (AWD) vốn là lệnh điều
khiển, nhật ký nông dân tự ghi trông như bằng chứng gần như miễn phí, xếp hạng cao
nhất theo Quyết định 4801/QĐ-BNNMT. Chúng tôi dựng lớp đó trên mô hình sinh đôi số
FAO-56 rồi tấn công nó; phần tấn công là đóng góp. Phát lại nhật ký với
ERA5 công khai phơi bày độ sâu không đất nào chứa được, nhưng đối thủ giữ
nguyên tổng lượng và từng độ sâu, chỉ dịch thời điểm lệnh, làm số pha khô được cấp tín
chỉ tăng $33\%$ (ghép cặp). Không lớp vật lý nào thoát hữu ích: bộ phát hiện
mô hình điểm kết tội oan $26{,}7\%$ nông dân trung thực, còn bộ bền vững giảm oan xuống
$5{,}0\%$ lại bỏ lọt phần lớn ca dịch thời điểm. Trên $281$ nhật ký tại ba trạm
Đồng bằng sông Cửu Long, hai năm khí hậu, đối chiếu với bản ghi lệnh có chữ ký, dấu thời gian của gateway bắt $116/116$ nhật ký giả, không oan ai. Vật lý không thể
đứng một mình; dấu thời gian phải do thiết bị cấp, không phải nông dân."""

# Cat theo thu tu: bo chu thua truoc (khong mat y), roi moi gop cau.
# Moi trim deu giu NGUYEN VEN 5 tu khoa va moi con so da verify (co assert o buoc 2).
VI_TRIMS = []

# LOI DA SUA (2026-10-09): ban cu de "MRV" trong danh sach nay, nen gate chi kiem
# viet tat co mat trong tom tat — trong khi tu khoa THUC SU duoc in o dong "Từ khóa:"
# cua bai la cum day du "đo đạc, báo cáo, thẩm định". He qua: tom tat VI dung "MRV"
# tran o lan dau, cum tu khoa khong xuat hien trong tom tat (vi pham quy dinh HUJOS
# "keywords need to be present in the abstract"), ma gate VAN XANH vi no kiem mot
# chuoi khac voi chuoi duoc in. Ban EN khong mac vi EN_KEYWORDS giu cum day du.
# NGUYEN TAC: danh sach tu khoa phai la ban sao cua dong duoc IN, khong viet tay.
VI_KEYWORDS = ["tưới khô ướt luân phiên", "đo đạc, báo cáo, thẩm định",
               "tín chỉ các-bon", "lúa phát thải thấp", "mô hình sinh đôi số"]

REQUIRED_EN = ["33", "26.7", "5.0", "281", "116/116", "4801", "FAO-56", "ERA5"]
REQUIRED_VI = ["33", "26", "5", "281", "116/116", "4801", "FAO-56", "ERA5"]


def fit(base: str, trims: list[tuple[str, str]], lang: str) -> tuple[str, list[str]]:
    """Cat dan theo thu tu cho toi khi <= LIMIT tu. Tra ve (text, nhat ky trim)."""
    t = base
    used, unmatched = [], []
    n = len(words(t))
    for old, new in trims:
        # LOI DA SUA (lan thu 6 vep cung mot lop loi trong session nay):
        # trim duoc viet dang r"...\n..." nen trong RAW string thi \n la CHU
        # backslash+n, khong phai xuong dong -> 4/8 trim im lang khong khop,
        # va khong co thong bao nao. Chuan hoa lai thanh newline that.
        old = old.replace(BS + "n", NL)
        new = new.replace(BS + "n", NL)
        if n <= LIMIT:
            break            # du roi, khong cat them de giu noi dung
        if old in t:
            t = t.replace(old, new)
            used.append(old[:52].replace(NL, " "))
            n = len(words(t))
        else:
            unmatched.append(old[:60].replace(NL, " "))
    print(f"  [{lang}] {len(words(base))} tu -> {n} tu sau {len(used)} trim")
    for u in used:
        print(f"        trim OK : {u}...")
    # KHONG duoc bo qua im lang: trim khong khop nghia la text da khac, phai biet.
    for u in unmatched:
        print(f"        !! KHONG KHOP: {u}...")
    if unmatched:
        raise SystemExit(f"[{lang}] {len(unmatched)} trim khong khop — "
                         f"doc lai text that roi sua, khong duoc bo qua")
    return t, used


print("=== BUOC 1: chuan bi 2 abstract ===")
en, en_used = fit(EN_BASE, EN_TRIMS, "EN")
vi, vi_used = fit(VI_BASE, VI_TRIMS, "VI")

print(f"{NL}=== BUOC 2: KIEM TRA TRUOC KHI GHI (khong ghi nua chung) ===")
errors = []

for lang, txt, kws, req in (("EN", en, EN_KEYWORDS, REQUIRED_EN),
                            ("VI", vi, VI_KEYWORDS, REQUIRED_VI)):
    n = len(words(txt))
    flat = re.sub(r"\s+", " ", txt)
    print(f"  [{lang}] {n} tu / tran 250 -> {'OK' if n <= LIMIT else 'VUOT'}")
    if n > 250:
        errors.append(f"{lang} vuot tran 250 tu: {n}")
    if n < 180:
        errors.append(f"{lang} ngat qua ngan ({n} tu), co the mat noi dung")
    miss_kw = [k for k in kws if k.lower() not in flat.lower()]
    print(f"  [{lang}] tu khoa thieu: {miss_kw or '(khong — du ca 5)'}")
    if miss_kw:
        errors.append(f"{lang} thieu tu khoa trong abstract: {miss_kw}")
    miss_num = [x for x in req if x not in flat]
    print(f"  [{lang}] con so thieu : {miss_num or '(khong — du het)'}")
    if miss_num:
        errors.append(f"{lang} thieu con so da verify: {miss_num}")

# ============================================================ GATE MOI 2026-10-09
# VIET TAT PHAI DUOC KHAI TRIEN O LAN DUNG DAU (academic-prose).
# Ly do gate nay ton tai: tom tat VI tung lot qua BUOC 2 voi "MRV" dung tran o cau
# dau, vi BUOC 2 chi kiem "tu khoa co mat trong tom tat" ma KHONG kiem "viet tat co
# duoc dinh nghia hay khong". Kiem tra theo dang bat buoc:
#     <cum khai trien> (<VIET TAT>)
# tuc dung hinh thuc dinh nghia tai cho, khong chap nhan khai trien o mot cau khac.
def fold_accent(t: str) -> str:
    """Gap dau tieng Viet de so sanh ma hieu: 'QĐ-BNNMT' == 'QD-BNNMT'.

    Can vi ban EN viet khong dau con ban VI viet co dau; neu khong gap thi cung mot
    ma quyet dinh bi gate coi la hai chuoi khac nhau va bao dong gia.
    """
    t = t.replace("Đ", "D").replace("đ", "d")   # Đ/đ khong phan ra NFD -> phai map tay
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii").upper()


# Dinh danh van ban quy pham phap luat VN: so/QĐ|NĐ|TT-BO, vd 4801/QĐ-BNNMT,
# 1490/QĐ-TTg, 26/2019/TT-BNNPTNT. Bat ca ca dang khong dau (QD) lan co dau (QĐ).
LEGAL_INSTRUMENT = re.compile(
    r"\d{1,5}(?:/\d{4})?/(?:Q[ĐD]|ND|NĐ|TT)-[A-ZĐa-zđ]{2,}(?:\d|[A-Za-zĐđ]+)*",
    re.I)

ACRONYM_DEFS = {
    "EN": {"MRV": ["Monitoring, reporting and verification"],
           "AWD": ["alternate wetting and drying"]},
    "VI": {"MRV": ["Đo đạc, báo cáo, thẩm định"],
           "AWD": ["tưới khô ướt luân phiên"]},
}
# Ten rieng / ma hieu khong can (va khong the) khai trien.
ACRONYM_EXEMPT = {"ERA5", "FAO-56", "VM0051", "IoT", "QĐ-BNNMT"}


def check_acronyms(lang: str, txt: str) -> list[str]:
    """Tra ve danh sach loi: viet tat dung ma khong co dang '<khai trien> (<viet tat>)'."""
    flat = re.sub(r"\s+", " ", txt)
    bad = []
    for acr, exps in ACRONYM_DEFS[lang].items():
        if not re.search(r"\b" + re.escape(acr) + r"\b", flat):
            continue                      # khong dung -> khong can dinh nghia
        ok = any(re.search(re.escape(e) + r"\s*\(\s*" + re.escape(acr) + r"\s*\)",
                           flat, re.I) for e in exps)
        if not ok:
            bad.append(f"{lang}: '{acr}' dung ma khong duoc khai trien tai cho "
                       f"(can mot trong: {exps} ({acr}))")
    # MA VAN BAN PHAP LY: dinh danh quyet dinh/nghi dinh/thong tu phai GIU NGUYEN
    # VAN, khong duoc "khai trien". Gate ma bat loi o day la bao dong gia, va neu
    # "sua" bang cach viet dai ra thi pha luat giu nguyen dinh danh van ban luat.
    legal = set()
    for m in re.finditer(LEGAL_INSTRUMENT, flat):
        whole = re.sub(r"\s+", " ", m.group(0))
        legal.add(whole); legal.add(fold_accent(whole))
        # tach ca '/' (so/bo) lan '-' (loai van ban - ten bo). Token ma gate quet ra
        # co the la 'QD-BNNMT' (ban EN) hoac chi 'BNNMT' (ban VI, vi 'QĐ' co chu Đ
        # khong nam trong lop ky tu [A-Za-z0-9] cua regex) — nen phai them ca hai.
        for part in re.split(r"[/\s-]", whole):
            if part:
                legal.add(part); legal.add(fold_accent(part))
        for piece in re.findall(r"[A-ZĐ]{2,}[A-Za-z0-9]*|[A-ZĐ][A-Za-z0-9]*", whole):
            legal.add(piece); legal.add(fold_accent(piece))
        # Ban EN viet 'Decision 4801/QD-BNNMT' nen token gate quet ra la CA CUM CO
        # GACH NOI ('QD-BNNMT'), trong khi cac buoc tren chi them 'QD' va 'BNNMT'
        # tach roi -> van bao dong gia. Them moi doan sau dau '/' va moi hau to
        # ghep bang gach noi cua no ('QD-BNNMT', 'BNNMT', 'TT-BNNPTNT', ...).
        for seg in whole.split("/"):
            seg = seg.strip()
            if not seg:
                continue
            legal.add(seg); legal.add(fold_accent(seg))
            pieces = seg.split("-")
            for k in range(len(pieces)):
                joined = "-".join(pieces[k:])
                if joined:
                    legal.add(joined); legal.add(fold_accent(joined))

    # viet tat la chu in hoa nao con lai trong tom tat phai nam trong mien tru
    for tok in set(re.findall(r"\b[A-Z][A-Za-z0-9]{1,}(?:-[A-Z0-9]+)*\b", flat)):
        if tok in ACRONYM_DEFS[lang]:
            continue
        if len(tok) <= 2 or not tok.isupper():
            continue
        if fold_accent(tok) in {fold_accent(x) for x in ACRONYM_EXEMPT}:
            continue                      # ERA5 / FAO-56 / VM0051 / IoT / QD-BNNMT
        if tok in legal or fold_accent(tok) in legal:
            continue                      # mot phan cua ma van ban luat
        bad.append(f"{lang}: '{tok}' la viet tat/tu viet hoa chua duoc dinh nghia "
                   f"va khong thuoc danh sach mien tru {sorted(ACRONYM_EXEMPT)}")
    return bad


for lang, txt in (("EN", en), ("VI", vi)):
    for e in check_acronyms(lang, txt):
        errors.append(e)
        print("  ! " + e)
    else:
        pass
print(f"  gate viet-tat-khai-trien: {'PASS' if not errors else 'FAIL'} (EN+VI)")

# DOI CHIEU TU KHOA IN THAT TRONG BAI (khong tin hang so viet tay).
# Day la lop chan thu hai: neu ai doi dong "Từ khóa:" trong .tex ma khong doi
# VI_KEYWORDS/EN_KEYWORDS thi gate nay bat duoc su lech nhau.
for lang, txt, fname, marker in (
        ("EN", en, str(H / "main_hujos.tex"), BS + "textbf{Keywords:}"),
        ("VI", vi, str(H / "main_hujos_vi.tex"), BS + "textbf{Từ khóa:}")):
    try:
        src = open(fname, encoding="utf-8").read()
    except OSError:
        print(f"  [{lang}] bo qua doi chieu tu khoa (khong doc duoc {fname})")
        continue
    k = src.find(marker)
    if k < 0:
        errors.append(f"{lang}: khong tim thay dong tu khoa trong {fname}")
        continue
    tail = src[k + len(marker):]
    stop = tail.find(BS + "vspace")
    line = re.sub(r"\s+", " ", tail[:stop if stop > 0 else 400]).strip().rstrip(".")
    printed = [x.strip() for x in re.split(r"[;]", line) if x.strip()]
    flat = re.sub(r"\s+", " ", txt).lower()
    miss = [x for x in printed if x.lower() not in flat]
    print(f"  [{lang}] tu khoa IN TRONG BAI ({len(printed)} cum): "
          f"{'tat ca deu co mat trong tom tat' if not miss else 'THIEU trong tom tat: ' + str(miss)}")
    if miss:
        errors.append(f"{lang}: tu khoa duoc in trong bai khong co mat trong tom tat: {miss}")

if errors:
    print(f"{NL}=== CHUA GHI GI VI CON LOI ===")
    for e in errors:
        print("  ! " + e)
    raise SystemExit(1)

print(f"{NL}=== BUOC 3: GHI FILE ===")
# ---- EN: thay tu '\noindent\textbf{Abstract.}' den truoc '\vspace{4pt}' cua Keywords
P = H / "main_hujos.tex"
s = P.read_text(encoding="utf-8")
ABS = BS + "noindent" + BS + "textbf{Abstract.}"
KW = BS + "noindent" + BS + "textbf{Keywords:}"
i0 = s.index(ABS)
k0 = s.index(KW)
v0 = s.rindex(BS + "vspace{4pt}", i0, k0)
new_s = s[:i0] + ABS + " " + en + NL + NL + "  " + s[v0:]
P.write_text(new_s, encoding="utf-8")
print(f"  main_hujos.tex: {len(s)} -> {len(new_s)} chars")

# ---- VI: thay tu SAU header muc den truoc '\textbf{Từ khóa:}'
# LOI DA SUA (2026-10-09): neo cu la t.index("MRV là nút thắt") — mot chuoi LAY
# TU NOI DUNG abstract. Khi abstract duoc sua de khai trien viet tat thanh
# "Đo đạc, báo cáo, thẩm định (MRV) là nút thắt..." thi neo khong con khop va
# script chet bang ValueError o LAN CHAY THU HAI (lan dau van chay duoc vi file
# luc do con giu ban cu). Day la loi "khong idempotent": script chi chay duoc
# mot lan sau moi lan sua noi dung. NGUYEN TAC: neo phai la CAU TRUC cua file
# (header muc / nhan tu khoa), khong bao gio la noi dung.
VI_HEAD = BS + "section*{Tóm tắt và từ khóa (Tiếng Việt)}"
VI_KW = BS + "textbf{Từ khóa:}"


def replace_between(text: str, start_marker: str, end_marker: str,
                    new_body: str, fname: str, indent: str = "") -> str:
    """Thay noi dung giua hai NEO CAU TRUC. Bao loi neu thieu bat ky neo nao."""
    a = text.find(start_marker)
    if a < 0:
        raise SystemExit(f"{fname}: khong tim thay neo bat dau {start_marker!r}")
    b = text.find(end_marker, a + len(start_marker))
    if b < 0:
        raise SystemExit(f"{fname}: khong tim thay neo ket thuc {end_marker!r}")
    body = new_body
    if indent:
        body = (indent + body.replace(NL, NL + indent))
    return text[:a + len(start_marker)] + NL + NL + body + NL + NL + text[b:]


Q = H / "blocks_vi.tex"
t = Q.read_text(encoding="utf-8")
new_t = replace_between(t, VI_HEAD, VI_KW, vi, "blocks_vi.tex")
Q.write_text(new_t, encoding="utf-8")
print(f"  blocks_vi.tex : {len(t)} -> {len(new_t)} chars")

# ---- main_hujos_vi.tex (BAN TIENG VIET DOC LAP): co abstract VI o DAU bai va
# abstract EN o CUOI bai, TRUOC DAY duoc chep TAY -> do la nguyen nhan EN/VI troi
# nhau (abstract VI tung mat cum khai trien MRV trong khi ban EN van dung).
# Tu nay script ghi ca ba cho, khong con ban chep tay.
R = H / "main_hujos_vi.tex"
if R.exists():
    u = R.read_text(encoding="utf-8")
    n0 = len(u)
    u = replace_between(u, BS + "noindent" + BS + "textbf{Tóm tắt.}",
                        BS + "noindent" + BS + "textbf{Từ khóa:}", vi,
                        "main_hujos_vi.tex (VI)", indent="  ")
    u = replace_between(u, BS + "noindent" + BS + "textbf{Abstract.}",
                        BS + "noindent" + BS + "textbf{Keywords:}", en,
                        "main_hujos_vi.tex (EN)", indent="  ")
    R.write_text(u, encoding="utf-8")
    print(f"  main_hujos_vi.tex: {n0} -> {len(u)} chars (ca VI dau bai + EN cuoi bai)")
else:
    print("  main_hujos_vi.tex: khong ton tai, bo qua")

# ---------------------------------------------------------------- BUOC 4: nhat quan than bai
print(f"{NL}=== BUOC 4: thuât ngu MRV trong than bai co nhat quan? ===")
bad = []
for f in sorted(B.glob("*.tex")):
    txt = f.read_text(encoding="utf-8", errors="replace")
    if re.search(r"Measurement, reporting and verification", txt, re.I):
        bad.append(f.name)
print(f"  file con dung 'Measurement, reporting and verification': {bad or '(khong)'}")
if bad:
    for f in bad:
        p = B / f
        txt = p.read_text(encoding="utf-8")
        n = len(re.findall(r"Measurement, reporting and verification", txt, re.I))
        txt2 = re.sub(r"Measurement, reporting and verification",
                      "Monitoring, reporting and verification", txt, flags=re.I)
        p.write_text(txt2, encoding="utf-8")
        print(f"    da sua {f}: {n} cho -> Monitoring (thuat ngu chuan, khop tu khoa)")

print(f"{NL}=== XONG ===")
