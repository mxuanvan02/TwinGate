#!/usr/bin/env python3
"""C2 -- tidal freshwater windows and source-water salinity (SCENARIO MODEL).

Khai bao trung thuc (bat buoc theo DESIGN_VN muc 3 va CHECKPOINT):
  Em KHONG CO so do man thuc dia 2024/2025 tai 3 tram. Moi con so EC trong file
  nay la THAM SO TINH HUONG (scenario), chuan theo thuc te cong khai ve dang
  (man dinh o trieu cuong, nhat o trieu kem; dinh xam nhap thang III-V), va
  BAT BUOC duoc quet do nhay (intrusion x EC_crit variant) thay vi khang dinh.
  Chi nguong EC_crit cua lua la co nguon cong bo (DESIGN_VN muc 5).

Cau truc mo hinh:
  * Trieu: ban nhat trieu tong hop, chu ky M2 = 12.4206 h (hang so vat ly chuan).
    norm(t) = cos(2*pi*(t+phase)/T); +1 = trieu cuong, -1 = trieu kem.
  * EC bang goc theo thang: ec_low[m] (luc trieu kem) va ec_high[m] (luc trieu
    cuong). Noi tuy theo pha trieu. Dang nay khop thuc te DBSCL: man dinh theo
    trieu cuong, nguoi dan "cho con nuoc" o trieu kem.
  * intrusion >= 0: boi so do manh xam nhap cua nam/tinh huong.
    EC_src = ec_river + intrusion * (ec_table - ec_river).
    intrusion = 0 => nguon ngot quanh nam; intrusion lon => man gat, cua so
    ngot bien mat => WITHHELD toan mua ("cho con nuoc" that bai).
  * EC_crit theo giai doan: Maas & Hoffman 1977 = 3.0 dS/m; Grattan et al. 2002
    (ars.usda.gov P1837.pdf) = 1.9 dS/m do thuc dia; USDA P572: ma nhay nhat,
    trổ CON TRANH CAI (Pearson & Bernstein vs Kaddah) => variant bat buoc quet.

Bang EC trung tam (central) la "nam xam nhap dien hinh", khong phai nam cuc
doan: Can Tho/Hau river mua kiet thuong 0.5-4 g/L (~0.8-6 dS/m), Soc Trang/Ca
Mau ven bien cao hon. Khac biet giua 3 tram duoc gom vao do bat dinh cua
intrusion sweep, khong khai bao rieng tung tram (khong co so do).

He qua thiet ke: ket qua dung module nay la PHAN TICH TINH HUONG, khong duoc
vao Abstract (quy tac (c) DESIGN_VN muc 3).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Principal lunar semidiurnal constituent M2: 12.4206 h (standard tidal constant).
M2_PERIOD_H = 12.4206

# Nuoc song mua kiet thuong nguon: 0.2-0.5 dS/m; 0.3 = giua.
EC_RIVER_DS_M = 0.3

# Bang EC tinh huong [dS/m] theo thang: (trieu kem, trieu cuong).
# DANG theo thuc te cong khai: dinh man III-V (mua kiet, dong thuong nguon thap),
# mua mua VI-XI gan nhu ngot. GIA TRI cu the la scenario -- quet qua `intrusion`.
EC_LOW_BY_MONTH = {
    1: 0.8, 2: 1.2, 3: 2.0, 4: 2.5, 5: 1.8, 6: 0.8,
    7: 0.4, 8: 0.3, 9: 0.3, 10: 0.3, 11: 0.4, 12: 0.6,
}
EC_HIGH_BY_MONTH = {
    1: 4.0, 2: 6.0, 3: 10.0, 4: 12.0, 5: 8.0, 6: 3.0,
    7: 1.5, 8: 1.0, 9: 0.6, 10: 0.5, 11: 0.8, 12: 1.5,
}

# Nguon: DESIGN_VN muc 5.
EC_CRIT_CENTRAL = {
    "seedling":        1.9,   # ma: nhay nhat, dung nguong do thuc dia chat hon
    "vegetative":      3.0,   # Maas & Hoffman
    "booting_heading": 3.0,   # tran cai -> giu 3.0, quet variant
    "flowering":       2.5,   # tran cai -> diem giua, KHONG duoc khang dinh
    "maturity":        3.5,   # chiu man tang dan khi chin
}
EC_VARIANTS = {
    "grattan_strict": 1.9 / 3.0,   # mo ca bang theo nguong do thuc dia 1.9
    "central":        1.0,
    "maas_lenient":   3.5 / 3.0,   # canh chiu man (USDA P572: chin chiu hon)
}
# Do doc thiet hai nang suat: -12% / (dS/m) tren nguong (ars.usda.gov P1837.pdf).
YIELD_LOSS_PER_DSM = 0.12


def stage_from_doy(doy: int) -> str:
    """Giai doan sinh truong vu Dong Xuan DBSCL theo ngay trong nam.

    Khai bao trung thuc: day la LICH THOI VU cong khai dang duoc dung cho DBSCL
    (gieo cay XI-XII, tro bông II-IV, chin IV-V), khong phai nien lich do duoc cho
    tung thua ruong. Cua so mo phong cua nghien cuu la thang III-V (mua kiet, dinh
    soc nhiet va dinh xam nhap man), tuc la cac giai doan trổ -> chin.
    """
    if doy < 60:            # ~ thang I-II: ma -> de nhanh
        return "seedling" if doy < 30 else "vegetative"
    if doy < 91:            # thang III: om dong - tro
        return "booting_heading"
    if doy < 121:           # thang IV: trổ - ngam sua
        return "flowering"
    if doy < 151:           # thang V: chin
        return "maturity"
    return "vegetative"     # vu he thu/mua: khong phai doi tuong cua cua so nay


@dataclass(frozen=True)
class TideModel:
    """Trieu ban nhat trieu tong hop: norm = cos(2pi (t+phase)/T_M2), [-1, +1].

    `t` la so gio ke tu moc (hang dau tien cua cua so mo phong). Pha la THAM SO
    TINH HUONG; chu ky M2 la hang so vat ly chuan.
    """
    phase_h: float = 0.0

    def norm(self, t_h: float) -> float:
        """Muc trieu chuan hoa trong [-1, 1]; +1 = trieu cuong (dinh), -1 = kem."""
        return math.cos(2.0 * math.pi * (t_h + self.phase_h) / M2_PERIOD_H)

    def period_hours(self) -> float:
        return M2_PERIOD_H


@dataclass(frozen=True)
class SalinityScenario:
    """Man nguon theo gio (SCENARIO): EC_src = ec_river + i*(ec_table - ec_river).

    ec_table noi tuyen tinh giua EC_low[m] (trieu kem) va EC_high[m] (trieu cuong)
    theo pha trieu. `intrusion` (i >= 0) la do manh xam nhap cua tinh huong:
      i = 0    -> nguon ngot quanh nam, cua so ngot 100%
      i = 1    -> nam xam nhap dien hinh (bang central)
      i >= 1.7 (mua kiet, central) -> EC trieu kem vuot 3.0: cua so ngot RONG
                  ca mua => WITHHELD toan bo ("cho con nuoc" that bai)
    Don dieu theo i va theo pha trieu -- ca hai duoc test.
    """
    tide: TideModel = TideModel()
    intrusion: float = 1.0
    ec_river: float = EC_RIVER_DS_M

    def ec_table(self, t_h: float, month: int) -> float:
        """EC bang goc (intrusion = 1) [dS/m] tai gio t."""
        if month not in EC_LOW_BY_MONTH:
            raise ValueError(f"month must be 1..12, got {month}")
        lo, hi = EC_LOW_BY_MONTH[month], EC_HIGH_BY_MONTH[month]
        frac_high = (1.0 + self.tide.norm(t_h)) / 2.0    # 0 = kem, 1 = cuong
        return lo + (hi - lo) * frac_high

    def ec_source(self, t_h: float, month: int) -> float:
        """EC cua nuoc nguon [dS/m] tai gio t, sau khi ap intrusion."""
        return self.ec_river + self.intrusion * (self.ec_table(t_h, month) - self.ec_river)

    def fresh_fraction_of_cycle(self, month: int, crit: float) -> float:
        """Phan chu ky trieu ma EC <= crit (giai tich, dung de doi chieu sim).

        EC_table(t) = lo + (hi-lo)*(1+cos(2pi t/T))/2 <= crit (voi intrusion=1)
        => cos <= 2*(crit-lo)/(hi-lo) - 1 =: c. Neu c >= 1: ca chu ky ngot;
        c <= -1: khong gio ngot; nguoc lai phan chu ky = 1 - arccos(c)/pi.
        Voi intrusion != 1, giai tren ec_river + i*(table - ec_river) <= crit
        <=> table <= crit + (1-i)*(table_crit...) -- don gian: quy doi crit' =
        ec_river + (crit - ec_river)/i.
        """
        i = self.intrusion
        if i <= 0:
            return 1.0 if self.ec_river <= crit else 0.0
        crit_t = self.ec_river + (crit - self.ec_river) / i
        lo, hi = EC_LOW_BY_MONTH[month], EC_HIGH_BY_MONTH[month]
        if crit_t >= hi:
            return 1.0
        if crit_t < lo:
            return 0.0
        c = 2.0 * (crit_t - lo) / (hi - lo) - 1.0
        return 1.0 - math.acos(max(-1.0, min(1.0, c))) / math.pi


def ec_crit(stage: str, variant: str = "central") -> float:
    """Nguong EC cua lua theo giai doan, co nguon (DESIGN_VN muc 5).

    `variant` dung cho quet do nhay vi giai doan trổ con tranh cai trong van lieu.
    """
    if stage not in EC_CRIT_CENTRAL:
        raise ValueError(f"unknown stage {stage!r}; known: {sorted(EC_CRIT_CENTRAL)}")
    if variant not in EC_VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; known: {sorted(EC_VARIANTS)}")
    return EC_CRIT_CENTRAL[stage] * EC_VARIANTS[variant]


def is_fresh(sc: SalinityScenario, t_h: float, month: int, stage: str,
             variant: str = "central") -> bool:
    """Nguon co du ngot de bom tai gio t hay khong (C2 point-in-time)."""
    return sc.ec_source(t_h, month) <= ec_crit(stage, variant)


def fresh_window(sc: SalinityScenario, t0_h: int, horizon_h: int,
                 month_of, stage_of, variant: str = "central") -> list[int]:
    """Cac gio trong [t0, t0+horizon) ma nguon du ngot de mo cong.

    Day chinh la "cho con nuoc": gateway phai doi den mot gio trong cua so nay,
    hoac WITHHELD neu khong co gio nao. `month_of(t)` -> month; `stage_of(month, t)`
    -> stage; module nay khong doc file thoi tiet.
    """
    out = []
    for h in range(horizon_h):
        t = t0_h + h
        month = month_of(t)
        if is_fresh(sc, t, month, stage_of(month, t), variant):
            out.append(t)
    return out


def salt_load_and_yield_loss(saline_mm: float, excess_dsm_mm: float) -> tuple[float, float]:
    """Uoc luong thiet hai neu bom nuoc man (chi dung cho tinh huong).

    `saline_mm`: tong do sau nuoc da bom luc EC > EC_crit.
    `excess_dsm_mm`: tong mm*(EC - EC_crit) cua luong do.
    Tra ve (EC vuot trung binh [dS/m], mat nang suat uoc tinh [%], DA CAP 100%).

    Do doc -12%/dS.m^-1 co nguon (ars.usda.gov P1837.pdf). CAP TAI 100% vi
    mat mua >100% la BAT KHA THI ve vat ly: do doc tuyen tinh chi co hieu luc
    trong vung EC vuot vua phai (toi da ~8.3 dS/m de cham 100%); ngoai vung do
    cay chet hoan toan, khong phai "mat 170% nang suat".

    LOI DA BAT (2026-10-03, sweep C2 full): ban dau tra ve 169.5%/172.7% o cac
    cell man gat -- do ngoai suy tuyen tinh vo han. `mean_excess` van duoc tra
    ve KHONG cap vi no la dai luong do duoc that (tong muoi), con % mat mua chi
    la dich thuc tho. Limitations phai ghi: dich nay la tuyen tinh + cap, khong
    phai mo hinh nang suat day du.
    """
    if saline_mm <= 0.0:
        return 0.0, 0.0
    mean_excess = excess_dsm_mm / saline_mm
    raw_loss = 100.0 * YIELD_LOSS_PER_DSM * mean_excess
    return mean_excess, min(100.0, raw_loss)
