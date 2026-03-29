"""
Financial Calculator — Tính thuế chuyển nhượng BĐS và khoản vay mua nhà.

Single Responsibility: Chỉ tính toán tài chính, không format/query.
Extracted from adapters.py.
"""
from __future__ import annotations

from typing import Dict

# ── Tax rates (source: Vietnamese tax law) ──
TAX_RATES: Dict[str, Dict] = {
    "thue_thu_nhap_ca_nhan": {
        "chuyen_nhuong_bds": 2.0,
        "description": "Thuế TNCN từ chuyển nhượng BĐS = 2% giá chuyển nhượng",
        "source": "Luật Thuế TNCN",
    },
    "le_phi_truoc_ba": {
        "nha_dat": 0.5,
        "description": "Lệ phí trước bạ nhà đất = 0.5% giá trị",
        "source": "Nghị định 10/2022/NĐ-CP",
    },
    "phi_cong_chung": {
        "duoi_50_trieu": 50000,
        "50_100_trieu": 100000,
        "100_1_ty": 500000,
        "1_3_ty": 1000000,
        "tren_3_ty": 2000000,
        "description": "Phí công chứng hợp đồng mua bán BĐS",
        "source": "Thông tư 257/2016/TT-BTC",
    },
    "phi_tham_dinh": {
        "gia_tri": 0.15,
        "toi_thieu": 100000,
        "toi_da": 50000000,
        "description": "Phí thẩm định hồ sơ cấp GCN = 0.15% giá trị (tối thiểu 100k, tối đa 50tr)",
        "source": "Thông tư 85/2019/TT-BTC",
    },
}


def calculate_transfer_tax(property_value: float) -> Dict:
    """
    Calculate taxes and fees for property transfer.

    Args:
        property_value: Property value in VND.

    Returns:
        Dict with tax breakdown: thue_tncn, le_phi_truoc_ba,
        phi_cong_chung, phi_tham_dinh, total, breakdown.
    """
    tncn = property_value * (TAX_RATES["thue_thu_nhap_ca_nhan"]["chuyen_nhuong_bds"] / 100)
    truoc_ba = property_value * (TAX_RATES["le_phi_truoc_ba"]["nha_dat"] / 100)
    cong_chung = _calculate_notary_fee(property_value)
    tham_dinh = _calculate_appraisal_fee(property_value)

    total = tncn + truoc_ba + cong_chung + tham_dinh

    return {
        "property_value": property_value,
        "thue_tncn": tncn,
        "le_phi_truoc_ba": truoc_ba,
        "phi_cong_chung": cong_chung,
        "phi_tham_dinh": tham_dinh,
        "total": total,
        "breakdown": {
            "Thuế TNCN (2%)": tncn,
            "Lệ phí trước bạ (0.5%)": truoc_ba,
            "Phí công chứng": cong_chung,
            "Phí thẩm định": tham_dinh,
        },
    }


def _calculate_notary_fee(property_value: float) -> float:
    """Calculate notary fee based on property value brackets."""
    phi_cc = TAX_RATES["phi_cong_chung"]
    if property_value < 50_000_000:
        return phi_cc["duoi_50_trieu"]
    elif property_value < 100_000_000:
        return phi_cc["50_100_trieu"]
    elif property_value < 1_000_000_000:
        return phi_cc["100_1_ty"]
    elif property_value < 3_000_000_000:
        return phi_cc["1_3_ty"]
    else:
        return phi_cc["tren_3_ty"]


def _calculate_appraisal_fee(property_value: float) -> float:
    """Calculate appraisal fee with min/max bounds."""
    phi_td = TAX_RATES["phi_tham_dinh"]
    tham_dinh = property_value * (phi_td["gia_tri"] / 100)
    return max(phi_td["toi_thieu"], min(tham_dinh, phi_td["toi_da"]))


def calculate_monthly_payment(
    loan_amount: float,
    interest_rate: float,
    term_months: int,
) -> Dict:
    """
    Calculate monthly loan payment (annuity formula).

    Args:
        loan_amount: Loan amount in VND.
        interest_rate: Annual interest rate (%).
        term_months: Loan term in months.

    Returns:
        Dict with monthly_payment, total_payment, total_interest.
    """
    monthly_rate = interest_rate / 100 / 12

    if monthly_rate == 0:
        monthly_payment = loan_amount / term_months
    else:
        monthly_payment = loan_amount * (
            (monthly_rate * (1 + monthly_rate) ** term_months)
            / ((1 + monthly_rate) ** term_months - 1)
        )

    total_payment = monthly_payment * term_months
    total_interest = total_payment - loan_amount

    return {
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "term_months": term_months,
        "monthly_payment": monthly_payment,
        "total_payment": total_payment,
        "total_interest": total_interest,
    }
