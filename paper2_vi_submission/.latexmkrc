# Bien dich ban nop (tieng Viet) — HUJOS-TT.
# Chay:  latexmk      ->  main.pdf (ngay canh main.tex)
#
# 1) ENGINE: BAT BUOC XeLaTeX. Ban thao dung fontspec + unicode-math cho font Unicode
#    tieng Viet (TeX Gyre Pagella), nen pdflatex / `latexmk -pdf` LUON that bai.
#    Tren Prism (prism.openai.com) engine duoc chon qua magic comment o DONG 1 cua
#    main.tex:  % !TEX program = xelatex   (viet HOA — Prism phan biet hoa thuong).
$pdf_mode = 5;                                  # 5 = xelatex
$xelatex  = 'xelatex -interaction=nonstopmode -synctex=1 %O %S';
$bibtex_use = 2;

# 2) MUC TIEU: chi co MOT tai lieu. Thieu dong nay thi `latexmk` tran tu bien dich
#    MOI file *.tex ke ca cac MANH \input (khong \documentclass, khong
#    \begin{document}) va bao "No counter 'proposition' defined" /
#    "Missing \begin{document}" / exit 12.
@default_files = ('main.tex');
