# Gói nguồn bản thảo — HUJOS-TT

**Một tài liệu duy nhất**: `src/main.tex` — thân bài và phụ lục S1–S21 nằm chung một
file (phụ lục được `\input` từ `src/supplementary_body.tex`), biên dịch ra
**`output/main.pdf`** (33 trang).

## Biên dịch

```bash
latexmk
```

PDF hiện ra ở `output/main.pdf`. Chạy lệnh này **từ thư mục gốc của gói** (nơi có
`.latexmkrc`) — file cấu hình đó đặt engine XeLaTeX, chỉ định duy nhất `src/main.tex`
làm mục tiêu, và xuất PDF vào `output/`.

> **Bắt buộc XeLaTeX.** Nếu gọi `pdflatex` hoặc `latexmk -pdf`, bản thảo dừng ngay với
> thông báo chỉ rõ cách sửa, vì font tiếng Việt Unicode cần gói `fontspec`.

### Biên dịch thủ công (khi máy không có latexmk)

```bash
cd src
xelatex -interaction=nonstopmode main.tex
bibtex main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

Cách này để PDF cạnh `src/main.tex` chứ không vào `output/`, vì `xelatex` thô không đọc
`.latexmkrc`. Cần 3 lần `xelatex` vì phụ lục dùng nhãn sinh từ `main.aux`.

## Cấu trúc thư mục

```
.
├── README.md                   ← file này
├── .latexmkrc                  XeLaTeX · chỉ build src/main.tex · PDF → output/
├── src/                        ← NGUỒN
│   ├── main.tex                TÀI LIỆU GỐC DUY NHẤT (thân bài + phụ lục)
│   ├── preamble.tex            khổ giấy, font, định lý, macro tiếng Việt
│   ├── supplementary_body.tex  nội dung phụ lục S1–S21 (main.tex \input)
│   ├── supplementary_stubs.tex nhãn tham chiếu chéo — TỰ SINH từ main.aux
│   ├── glossary.tex            bảng thuật ngữ Anh–Việt
│   ├── refs.bib                tài liệu tham khảo (BibTeX)
│   ├── vancouver.bst           kiểu trích dẫn (kèm sẵn phòng bản TeX tối giản)
│   ├── sections/               9 chương thân bài
│   ├── tables/                 9 bảng số
│   └── figures/                3 hình
└── output/main.pdf             ← KẾT QUẢ
```

Mọi tệp trong gói đều là **tệp thật**, không có liên kết mềm (symlink), nên giải nén ở
máy khác vẫn biên dịch được.

## Sau khi đổi số chương / mục / bảng

`src/supplementary_stubs.tex` là **file tự sinh**, không sửa tay. Build lại `main.tex`
rồi chạy `python3 experiments/make_supp_stubs.py` (script tự tìm `main.aux` ở cả
`output/` lẫn `src/`).

## Yêu cầu hệ thống

- TeX Live 2021+, có `texlive-xetex` và `texlive-fonts-extra`
- Gói đã dùng (đều có trong TeX Live chuẩn): `fontspec`, `unicode-math`, `amsmath`,
  `amsthm`, `booktabs`, `caption`, `natbib`, `geometry`, `titlesec`, `fancyhdr`,
  `hyperref`, `graphicx`, `microtype`, `array`, `url`, `xspace`, `placeins`,
  `appendix`, `iftex`
- Font: `TeX Gyre Pagella`, `TeX Gyre Pagella Math` — kiểm tra bằng
  `fc-list "TeX Gyre Pagella"`

## Kiểm tra sau khi biên dịch

```bash
grep -c '^!' output/main.log                 # = 0  (không lỗi)
grep -ci undefined output/main.log           # = 0  (không tham chiếu treo)
pdftotext output/main.pdf - | grep -c '??'   # = 0  (không nhãn chưa giải)
pdfinfo output/main.pdf | grep Pages         # = 33
```
