# Gói nguồn bản thảo — HUJOS-TT

**Một tài liệu duy nhất**: `main.tex` — thân bài và phụ lục S1–S21 nằm chung một file
(phụ lục được `\input` từ `supplementary_body.tex`), biên dịch ra **`main.pdf`**
(35 trang).

> **Toàn bộ file nằm phẳng ở một cấp, không có thư mục con.** Lý do: một số trình
> biên dịch trực tuyến (ví dụ Prism – prism.openai.com) làm phẳng gói khi nhập và
> **bỏ qua thư mục lồng nhau**, khiến `\input{sections/01_intro}` không tìm thấy file
> và báo `Emergency stop. (job aborted, no legal \end found)`.

## Biên dịch

### Trên Prism (prism.openai.com)

1. Tạo project mới, **xoá sạch** nội dung mẫu.
2. Kéo-thả **tất cả** file `.tex`, `.bib`, `.bst`, `.png` trong gói này vào.
3. Mở `main.tex`. Dòng đầu tiên đã có sẵn magic comment chọn engine:
   ```latex
   % !TEX program = xelatex
   ```
   **Không đổi dòng này.** Prism mặc định dùng pdfLaTeX; thiếu magic comment (hoặc
   viết thường `% !TeX`) thì Prism sẽ biên dịch bằng pdfLaTeX và bài này **không**
   biên dịch được vì cần `fontspec` cho font tiếng Việt Unicode.
4. Bấm Render.

Nếu Prism báo lỗi kiểu *File ... not found*, kiểm tra đã kéo **đủ 29 file** chưa
(danh sách ở mục "Nội dung gói" bên dưới).

### Trên máy có TeX Live

```bash
latexmk
```

PDF hiện ra cạnh `main.tex`. File `.latexmkrc` kèm theo đã đặt engine XeLaTeX và chỉ
định `main.tex` làm mục tiêu duy nhất.

### Biên dịch thủ công

```bash
xelatex -interaction=nonstopmode main.tex
bibtex main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

Cần 3 lần `xelatex` vì phụ lục dùng nhãn tham chiếu chéo sinh từ `main.aux`.

> **Bắt buộc XeLaTeX.** Nếu gọi `pdflatex`, bản thảo dừng ngay với thông báo chỉ rõ
> cách sửa (không phải lỗi khó hiểu), vì font tiếng Việt Unicode cần gói `fontspec`.

## Nội dung gói (29 file, tất cả ở một cấp)

| Nhóm | File |
|---|---|
| Tài liệu gốc | `main.tex` (thân bài + phụ lục) |
| Cấu hình | `preamble.tex` (khổ giấy, font, định lý, macro tiếng Việt) |
| Phụ lục | `supplementary_body.tex` (nội dung S1–S21), `supplementary_stubs.tex` (nhãn tham chiếu chéo — **tự sinh**, không sửa tay) |
| Thuật ngữ | `glossary.tex` |
| Tài liệu tham khảo | `refs.bib`, `vancouver.bst` |
| 9 chương thân bài | `01_intro.tex`, `02_threat_attack.tex`, `03_guarantee.tex`, `04_anchor.tex`, `05_design_results.tex`, `06_discussion_conclusion.tex`, `07_system_model.tex`, `08_subsidence.tex`, `09_cost.tex` |
| 9 bảng số | `tab_baseline.tex`, `tab_benchmark.tex`, `tab_credit.tex`, `tab_defence.tex`, `tab_f2_unreachable.tex`, `tab_false_accusation.tex`, `tab_setup.tex`, `tab_threat.tex`, `tab_umax.tex` |
| 3 hình | `fig1_method.png`, `fig2_tradeoff.png`, `fig3_timeshift.png` |
| Khác | `README_BUILD.md`, `.latexmkrc` |

## Sau khi đổi số chương / mục / bảng

`supplementary_stubs.tex` là file **tự sinh**, không sửa tay. Build lại `main.tex` rồi
chạy `python3 experiments/make_supp_stubs.py`.

## Yêu cầu hệ thống (khi build trên máy riêng)

- TeX Live 2021+, có `texlive-xetex` và `texlive-fonts-extra`
- Gói đã dùng (đều có trong TeX Live chuẩn): `fontspec`, `unicode-math`, `amsmath`,
  `amsthm`, `booktabs`, `caption`, `natbib`, `geometry`, `titlesec`, `fancyhdr`,
  `hyperref`, `graphicx`, `microtype`, `array`, `url`, `xspace`, `placeins`,
  `appendix`, `iftex`
- Font: `TeX Gyre Pagella`, `TeX Gyre Pagella Math` — kiểm tra bằng
  `fc-list "TeX Gyre Pagella"`

## Kiểm tra sau khi biên dịch

```bash
grep -c '^!' main.log                 # = 0  (không lỗi)
grep -ci undefined main.log           # = 0  (không tham chiếu treo)
pdftotext main.pdf - | grep -c '??'   # = 0  (không nhãn chưa giải)
pdfinfo main.pdf | grep Pages         # = 35
```
