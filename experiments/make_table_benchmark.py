#!/usr/bin/env python3
"""Sinh bang LaTeX 'tab_benchmark' tu outputs/_benchmark_summary.json.

Bang nay la thu anh Van yeu cau: "ket qua phai chay so sanh voi benchmark, SOTA
moi la minh chung de su dung duoc". Truoc do bai chi LAP LUAN rang ve tinh
khong phan giai duoc pha kho 72h (06_discussion_conclusion.tex, muc 'Relation to
remote sensing'). Bay gio con so duoc DO tren 60 trajectory / 150 pha kho that.

NGUON SO: experiments/benchmark_confirmation.py -> outputs/_benchmark_summary.json
KHONG doc tu benchmark_mrv.csv, vi file do chi con 23/60 trajectory sau khi loc
nhat ky <3 lenh (selection bias). Cot 'xac nhan' khong dung nhat ky nao nen phai
tinh tren TOAN BO mau.

TRUNG THUC VE GIOI HAN (ghi ngay trong caption de reviewer khong phai doan):
  * IoT va ban ghi lenh deu ra 100% o cot nay. Chung KHONG tuong duong: khac nhau
    ve chi phi (1 thiet bi/thua vs 0, vi controller da ton tai) va ve kha nang
    phat hien gian lan. Cot nay chi do kha nang CAP TIN CHI.
  * Anh + tu khai = 0% khong co nghia la phuong an do vo dung; no co nghia la no
    khong tao ra chuoi quan sat doi chieu duoc voi pha kho, nen moi su xac nhan
    deu phai qua kiem tra thuc dia.
  * revisit 6/12 ngay lay tu nguon da verify Crossref, khong tu dat.

Chay: python3 experiments/make_table_benchmark.py [dest_dir] [col_budget_cm]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SUMM = OUT / "_benchmark_summary.json"

BS = chr(92)                 # mot backslash. KHONG viet "\\" trong string khong raw.
NL = "\n"
TABCOLSEP_CM = 3 * 2 * 0.0352778      # 3pt moi ben, doi ra cm


def rule(kind: str) -> str:
    return BS + {"top": "toprule", "mid": "midrule", "bot": "bottomrule"}[kind]


def row(*cells) -> str:
    return " & ".join(str(c) for c in cells) + " " + BS + BS


def main(dest: Path, budget_cm: float) -> int:
    if not SUMM.exists():
        raise SystemExit(f"thieu {SUMM.name}: chay experiments/benchmark_confirmation.py truoc")
    d = json.loads(SUMM.read_text(encoding="utf-8"))
    rows = d["rows"]
    n, tot = d["n_traj"], d["tot_phase"]
    print(f"=== nguon: {SUMM.name} | {n} trajectory | {tot} pha kho that "
          f"| trung binh {d['mean_phase']} pha/trajectory")

    header = ["Verification route",
              f"Confirmable dry phases ($n={tot}$)",
              "Observations per season",
              "Devices per plot"]
    lines = [rule("top"), row(*header), rule("mid")]
    for r in rows:
        cite = r["cite"]
        lbl = r["label"] + (f"~{BS}cite{{{cite}}}" if cite else "")
        conf = f"{r['confirm']}/{r['total']} ({r['pct']}" + BS + "%)"
        obs = "---" if not r["obs"] else f"{r['obs']:,}"
        lines.append(row(lbl, conf, obs, r["cost"]))
    lines.append(rule("bot"))

    spec = [("p", 4.30), ("c", 2.90), ("c", 2.30), ("c", 2.30)]
    total = sum(w for _, w in spec) + TABCOLSEP_CM * (len(spec) - 1)
    if total > budget_cm + 1e-9:
        raise SystemExit(f"tran khung: tong cot {total:.2f}cm > ngan sach {budget_cm:.2f}cm")
    # LOI DA SUA: f-string cu viet "f>{{>{BS}raggedright..." -> {{{{ }}} cho ra '{'
    # roi them mot '>' thua, nen bang sinh ra co '>{{>\raggedright...'. LaTeX van
    # bien dich duoc (QA overfull/so trang khong bat) nhung se IN RA DAU '>' rac
    # truoc moi nhan dong. Doi chieu voi bieu thuc dang chay tot o
    # make_tables_anchored.py dong 77: ">{\" + BS + "raggedright" + ...
    cols = [f">{{{BS}raggedright{BS}arraybackslash}}p{{{w:.2f}cm}}" if k == "p" else k
            for k, w in spec]
    begin = BS + "begin{tabular}{@{}" + "".join(cols) + "@{}}"
    inner = NL.join([begin] + lines + [BS + "end{tabular}"])
    tex = (f"% Sinh TU DONG tu outputs/_benchmark_summary.json boi "
           f"experiments/make_table_benchmark.py{NL}"
           f"% KHONG sua tay: moi con so truy nguon ve benchmark_confirmation.py.{NL}{NL}"
           f"{BS}fittocol{{{NL}{inner}{NL}}}{NL}")
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "tab_benchmark.tex"
    out.write_text(tex, encoding="utf-8")
    print(f"  xuat {out.relative_to(ROOT)}")
    print(f"    tong cot {total:.2f}cm <= ngan sach {budget_cm:.2f}cm -> OK")
    for r in rows:
        print(f"    {r['label']:<40} {r['confirm']:>4}/{r['total']} = {r['pct']:>3}% "
              f"| obs {r['obs']:>5} | {r['cost']}")

    # ---- GATE: bang phai noi duoc dieu bai can noi ----
    ab = next(r for r in rows if r["tag"] == "s1ab")
    a1 = next(r for r in rows if r["tag"] == "s1a")
    iot = next(r for r in rows if r["tag"] == "iot")
    anc = next(r for r in rows if r["tag"] == "anchor")
    ph = next(r for r in rows if r["tag"] == "photo")
    assert ab["confirm"] != a1["confirm"], (
        "Sentinel 6 ngay va 12 ngay cho cung ket qua -> tag va cham (bug da sua mot lan)")
    assert ph["confirm"] == 0, "anh + tu khai phai ra 0% (khong co chuoi quan sat)"
    assert iot["pct"] == anc["pct"] == 100, (
        f"ca hai phuong quan sat lien tuc deu phai dat 100%: iot={iot['pct']} "
        f"anchor={anc['pct']}")
    assert ab["pct"] > a1["pct"], "chup mau hon phai xac nhan duoc nhieu hon"
    assert 0 < a1["pct"] < 100, (
        f"ban 12 ngay phai o GIUA 0 va 100 de chung to diem mu thuc su ton tai: {a1['pct']}")
    print(f"{NL}  GATE bang: PASS (6 ngay > 12 ngay > anh; 12 ngay o giua 0 va 100 "
          f"-> diem mu that su ton tai)")
    return 0


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper2_hujos" / "tables"
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    sys.exit(main(dest, budget))
