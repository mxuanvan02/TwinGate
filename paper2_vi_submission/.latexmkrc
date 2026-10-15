# Bien dich ban nop (tieng Viet) — HUJOS-TT.
# Chay:  latexmk        (khong can tham so)  ->  output/main.pdf
#
# 1) ENGINE: BAT BUOC XeLaTeX. Ban thao dung fontspec + unicode-math cho font Unicode
#    tieng Viet (TeX Gyre Pagella), nen pdflatex / `latexmk -pdf` LUON that bai voi
#    "Fatal Package fontspec Error".
$pdf_mode = 5;                                  # 5 = xelatex
$xelatex  = 'xelatex -interaction=nonstopmode -synctex=1 %O %S';
$bibtex_use = 2;

# 2) MUC TIEU: chi co MOT tai lieu. Thieu dong nay thi `latexmk` tran tu bien dich MOI
#    file *.tex ke ca cac MANH \input (khong \documentclass, khong \begin{document})
#    va bao "No counter 'proposition' defined" / "Missing \begin{document}" / exit 12.
@default_files = ('src/main.tex');

# 3) THU MUC LAM VIEC: nguon nam trong src/, nen latexmk phai cd vao do thi
#    \input{preamble} va \includegraphics{figures/...} moi tim thay file.
$do_cd = 1;

# 4) OUTPUT: PDF va file trung gian nam trong output/ de src/ luon sach.
#    Sau khi cd, duong dan tuong doi tinh tu src/ -> phai dung duong dan TUYET DOI.
#    Chu y: bien $PWD khong ton tai trong rc file (Perl) -> dung Cwd::abs_path.
use Cwd qw(abs_path);
$out_dir = abs_path('.') . '/output';
