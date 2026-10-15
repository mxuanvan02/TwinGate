# Bien dich ban thao HUJOS tieng Viet.
#
# 1) ENGINE: BAT BUOC XeLaTeX. Ban thao dung fontspec + unicode-math cho font Unicode
#    tieng Viet (TeX Gyre Pagella), nen pdflatex/latexmk -pdf LUON that bai voi
#    "Fatal Package fontspec Error". pdf_mode=5 dat xelatex lam engine mac dinh.
$pdf_mode = 5;          # 5 = xelatex
$xelatex  = 'xelatex -interaction=nonstopmode -synctex=1 %O %S';
$bibtex_use = 2;        # chay bibtex va don file trung gian khi build xong

# 2) MUC TIEU: chi build 2 TAI LIEU that su can nop.
#    Ly do: thu muc nay chua cac MANH \input (preamble.tex, supp_body_vi.tex,
#    supp_stubs_vi.tex) khong phai tai lieu doc lap — chung khong co \documentclass
#    va khong co \begin{document}. Neu khong khai bao @default_files thi `latexmk`
#    tran se tu bien dich MOI file *.tex nhu mot tai lieu rieng va bao loi
#    "No counter 'proposition' defined" / "Missing \begin{document}" / "Emergency stop".
#    Cac loi do khong phai loi cua ban thao; chung den tu viec build nham manh.
@default_files = ('main_hujos_vi.tex', 'supplementary_vi.tex');
