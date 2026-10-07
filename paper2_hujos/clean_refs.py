#!/usr/bin/env python3
"""Dọn 8 entry trong refs.bib TRƯỚC khi nộp HUJOS.

Hai loại lỗi, đều tìm thấy bằng cách đọc .bbl đã render (không phải đoán):

A) GHI CHÚ NỘI BỘ / VẬN HÀNH lọt vào danh sách tài liệu. Anh Văn đã quy định bản
   nộp không chứa ghi chú nội bộ, placeholder hay trạng thái verify. Cụ thể:
     - qd4801   : "Ngày 14/11/2025. sha256 557b9a6d… (refs/QD4801_2025.pdf)."
     - vm0051   : "sha256 9b973884… (refs/VM0051_v1.1.pdf)"
     - fao56    : "Sách FAO, không DOI riêng."
     - qd1490   : "Ngày 27/11/2023. vanban.chinhphu.vn docid=209054."
     - rabs     : "Đang phản biện, STAIS 2026."
     - cawvou   : "Đã nộp, IEEE Internet of Things Journal."
     - twingate2026: "Under review, Hue University Journal of Science --
                      Techniques and Technology" — vừa là trạng thái vận hành,
                      vừa xướng tên CHÍNH tạp chí đang nộp.
   sha256 + đường dẫn refs/*.pdf là bằng chứng nội bộ phục vụ kiểm tra nguồn,
   có giá trị với ta nhưng không phải một phần của trích dẫn học thuật.

B) SAI DỮ LIỆU THƯ MỤC. mlrice2025 khai author = {{Anonymous}} và title bị cắt
   cụt. arXiv:2507.08605 là bài có thật, 9 tác giả, tiêu đề đầy đủ dài hơn.
   Trích dẫn một bài có tác giả thật là "Anonymous" là lỗi nghiêm trọng hơn lỗi
   hình thức, nên script này TỰ fetch metadata từ arXiv API thay vì để tôi gõ lại
   tên tác giả từ trí nhớ.

Kèm sửa: fao56 đặt `publisher = {FAO Irrigation and Drainage Paper 56}` — đó là
tên SERIES chứ không phải nhà xuất bản. Tách thành series + publisher + address.

Lưu ý: refs.bib được DÙNG CHUNG giữa bản IEEE (paper2/) và bản HUJOS
(paper2_hujos/refs.bib là symlink), nên sửa một lần có tác dụng cho cả hai.
"""
from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path

UA = {"User-Agent": "ref-check/1.0 (mailto:ntuongtri@hueuni.edu.vn)"}
P = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2/refs.bib")
bib = P.read_text(encoding="utf-8")
n0 = len(bib)


def replace_entry(key: str, new_entry: str) -> None:
    """Thay NGUYÊN entry @type{key, ... } — không sửa từng field."""
    global bib
    pat = re.compile(r"@\w+\{" + re.escape(key) + r",.*?\n\}", re.S)
    found = pat.findall(bib)
    assert len(found) == 1, f"{key}: thay {len(found)} lan (mong 1)"
    bib = pat.sub(lambda m: new_entry, bib, count=1)
    print("  OK " + key)


# ---------------------------------------------------------------- B) mlrice2025
print("=== fetch arXiv:2507.08605 de lay metadata that ===")
req = urllib.request.Request(
    "http://export.arxiv.org/api/query?id_list=2507.08605", headers=UA)
with urllib.request.urlopen(req, timeout=90) as r:
    atom = r.read().decode("utf-8", "ignore")

entries = re.findall(r"<entry>(.*?)</entry>", atom, re.S)
assert len(entries) == 1, f"arXiv tra ve {len(entries)} entry"
e = entries[0]
title = html.unescape(re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1))).strip()
authors = [html.unescape(a) for a in re.findall(r"<name>(.*?)</name>", e, re.S)]
assert authors and "Anonymous" not in authors, "arXiv khong tra ve tac gia that"
print(f"  title   : {title}")
print(f"  authors : {len(authors)} -> {authors[0]} ... {authors[-1]}")

auth_bib = " and ".join(a.replace(" ", ", ", a.count(" ")) if a.count(" ") == 1
                        else ", ".join([a.split()[-1]] + [" ".join(a.split()[:-1])])
                        for a in authors)
# don gian va an toan hon: dung dang "Given Family" ghep bang ' and '
auth_bib = " and ".join(
    (lambda p: f"{p[-1]}, {' '.join(p[:-1])}")(a.split()) for a in authors)
print(f"  bibtex  : {auth_bib[:96]} ...")

replace_entry("mlrice2025", f"""@misc{{mlrice2025,
  author       = {{{auth_bib}}},
  title        = {{{title}}},
  year         = {{2025}},
  eprint       = {{2507.08605}},
  archivePrefix= {{arXiv}},
  primaryClass = {{cs.LG}},
  note         = {{arXiv preprint arXiv:2507.08605}}
}}""")

# ---------------------------------------------------------------- A) ghi chu noi bo
replace_entry("qd4801", """@misc{qd4801,
  author = {{Bộ Nông nghiệp và Môi trường}},
  title  = {Quyết định 4801/QĐ-BNNMT: Quy trình thí điểm Đo đạc, báo cáo, thẩm định (MRV) trong canh tác lúa chất lượng cao, phát thải thấp vùng Đồng bằng sông Cửu Long},
  year   = {2025},
  note   = {Hanoi, Viet Nam, 14 November 2025}
}""")

replace_entry("vm0051", """@misc{vm0051,
  author       = {{Verra}},
  title        = {VM0051 Improved Management in Rice Production Systems, Version 1.1},
  year         = {2026},
  howpublished = {\\url{https://verra.org}},
  note         = {Effective 14 July 2026}
}""")

replace_entry("twingate2026", """@unpublished{twingate2026,
  author = {Mai, Xuan Van and Nguyen, Tuong Tri},
  title  = {A Digital-Twin Safety Gate for Irrigation Command Dispatch over Lossy Networks and Its Relevance to Emission {MRV}},
  year   = {2026},
  note   = {Manuscript under review}
}""")

replace_entry("fao56", """@book{fao56,
  author    = {Allen, Richard G. and Pereira, Luis S. and Raes, Dirk and Smith, Martin},
  title     = {Crop Evapotranspiration --- Guidelines for Computing Crop Water Requirements},
  series    = {FAO Irrigation and Drainage Paper 56},
  publisher = {Food and Agriculture Organization of the United Nations},
  address   = {Rome},
  year      = {1998},
  isbn      = {92-5-104219-5}
}""")

replace_entry("qd1490", """@misc{qd1490,
  author = {{Thủ tướng Chính phủ}},
  title  = {Quyết định 1490/QĐ-TTg: Phê duyệt Đề án ``Phát triển bền vững một triệu héc-ta chuyên canh lúa chất lượng cao và phát thải thấp gắn với tăng trưởng xanh vùng đồng bằng sông Cửu Long đến năm 2030''},
  year   = {2023},
  note   = {Hanoi, Viet Nam, 27 November 2023}
}""")

replace_entry("rabs", """@unpublished{rabs,
  author = {Mai, Xuan Van and Le, Duc Minh Phuong and Dang, Tri Nguyen and Truong, Khanh Duy and Duong, Duc Giap and Nguyen, Tuong Tri},
  title  = {Self-Tuning Risk-Adaptive Bandwidth Scaling for Safety-Critical Smart-Agriculture {IoT} Networks},
  year   = {2026},
  note   = {Manuscript under review}
}""")

replace_entry("cawvou", """@unpublished{cawvou,
  author = {Mai, Xuan Van and Le, Duc Minh Phuong and Dang, Tri Nguyen and Truong, Khanh Duy and Nguyen, Hoang Son and Nguyen, Tuong Tri},
  title  = {Threshold-Aware Probe-Then-Transmit Scheduling for Safety-Critical {IoT} Monitoring},
  year   = {2026},
  note   = {Manuscript under review}
}""")

P.write_text(bib, encoding="utf-8")
print(f"\nrefs.bib: {n0} -> {len(bib)} chars")

# ---------------------------------------------------------------- CHOT CHAN
print("\n=== CHOT CHAN: quet lai con ghi chu noi bo trong ENTRY? ===")
# PHAI BO QUA DONG COMMENT. Ban gate dau quet ca file nen bat nham dong 2 cua
# refs.bib la mot comment header ('% Muc nao khong DOI that ... KHONG bia DOI'),
# tuc la mot QUY UOC tot dang duoc giu, khong phai note cua entry nao.
BAD = ["sha256", "refs/", "docid", "Đang phản biện", "Đã nộp", "không DOI",
       "Sách FAO", "Anonymous", "Under review, Hue", "vanban.chinhphu.vn"]
body = "\n".join(l for l in bib.split("\n") if not l.lstrip().startswith("%"))
left = [(b, len(re.findall(re.escape(b), body))) for b in BAD if b in body]
for b, n in left:
    print(f"  !! con {n} lan trong entry: {b}")
if not left:
    print("  SACH — khong con ghi chu noi bo / placeholder nao trong entry")
    # xac nhan mlrice2025 da co tac gia that
    m = re.search(r"@misc\{mlrice2025,.*?\n\}", bib, re.S)
    assert m and "Shah, Ando" in m.group(0), "mlrice2025 chua duoc sua dung"
    assert "Anonymous" not in m.group(0), "mlrice2025 van con Anonymous"
    print("  OK mlrice2025 co 9 tac gia that (Shah, Ando ... Lavista Ferres)")
    sys.exit(0)
sys.exit(1)
