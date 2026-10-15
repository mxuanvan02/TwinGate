# Cách biên dịch bản thảo này

**BẮT BUỘC dùng XeLaTeX.** Bản thảo dùng font Unicode tiếng Việt (TeX Gyre Pagella)
qua `fontspec` + `unicode-math`, nên `pdflatex` **không** biên dịch được.

## Cách nhanh nhất

```bash
latexmk
```

Thư mục này có sẵn `.latexmkrc` làm hai việc:

1. `$pdf_mode = 5` — dùng XeLaTeX, chạy đủ số lần để giải tham chiếu chéo + tài liệu
   tham khảo.
2. `@default_files` — chỉ biên dịch **hai tài liệu cần nộp**
   (`main_hujos_vi.tex`, `supplementary_vi.tex`).

Điểm 2 quan trọng: thư mục có các **mảnh `\input`** (`preamble.tex`,
`supp_body_vi.tex`, `supp_stubs_vi.tex`) không phải tài liệu độc lập — chúng không có
`\documentclass` và không có `\begin{document}`. Nếu thiếu `@default_files`, lệnh
`latexmk` trần sẽ tự biên dịch *mọi* tệp `.tex` như một tài liệu riêng và báo

```
! LaTeX Error: No counter 'proposition' defined.
! LaTeX Error: Missing \begin{document}.
! Emergency stop.
```

Những lỗi đó **không phải lỗi của bản thảo** — chúng đến từ việc biên dịch nhầm mảnh.

> Nếu bạn chạy `latexmk -pdf` (chế độ pdflatex) thì sẽ **lỗi** — đó là hành vi đúng.
> Hãy chạy `latexmk` trần, hoặc `latexmk -xelatex`.

## Cách thủ công (4 bước cho mỗi tài liệu)

```bash
xelatex -interaction=nonstopmode main_hujos_vi.tex
bibtex main_hujos_vi
xelatex -interaction=nonstopmode main_hujos_vi.tex
xelatex -interaction=nonstopmode main_hujos_vi.tex
```

Cần chạy `xelatex` **3 lần** vì bài có tham chiếu chéo (`\ref`) và phụ lục dùng nhãn
sinh từ tệp `.aux` của bài chính.

## Hai tài liệu trong gói này

| Tệp gốc | Kết quả | Nội dung |
|---|---|---|
| `main_hujos_vi.tex` | 33 trang | **Bản gộp**: thân bài + phụ lục S1–S21 (nộp dạng một tệp) |
| `supplementary_vi.tex` | 13 trang | **Phụ lục riêng** (nộp dạng tệp tách rời) |

Cả hai dùng chung một nguồn phụ lục là `supp_body_vi.tex`, nên không có nội dung bị
nhân đôi hay lệch nhau giữa hai bản.

## Yêu cầu hệ thống

- TeX Live 2021 trở lên, đã cài `texlive-xetex` và `texlive-fonts-extra`
- Các gói đã dùng (đều có trong TeX Live chuẩn): `fontspec`, `unicode-math`, `amsmath`,
  `amsthm`, `booktabs`, `caption`, `natbib`, `geometry`, `titlesec`, `fancyhdr`,
  `hyperref`, `graphicx`, `microtype`, `array`, `url`, `xspace`, `placeins`, `appendix`
- Font: `TeX Gyre Pagella` và `TeX Gyre Pagella Math`
  (kiểm tra bằng `fc-list "TeX Gyre Pagella"`)
- Kiểu tài liệu tham khảo: `vancouver` (`kpsewhich vancouver.bst`). Gói này kèm sẵn
  trong TeX Live; tệp `vancouver.bst` cũng được bỏ vào thư mục này để phòng trường hợp
  bản cài tối giản không có nó.

## Kiểm tra sau khi biên dịch

Log phải thoả:

```bash
grep -c '^!' main_hujos_vi.log              # = 0  (không lỗi)
grep -ci 'undefined' main_hujos_vi.log      # = 0  (không tham chiếu treo)
pdftotext main_hujos_vi.pdf - | grep -c '??'  # = 0 (không nhãn chưa giải)
```

Nếu bạn nhận được `! Fatal Package fontspec Error: The fontspec package requires
either XeTeX or LuaTeX`, nghĩa là trình biên dịch đang gọi nhầm engine. Dùng lệnh ở
mục trên.
