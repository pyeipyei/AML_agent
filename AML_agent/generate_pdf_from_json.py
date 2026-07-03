"""
Generate a KYC Assessment Form PDF from company.json and screening_results.json.

Usage:
    python generate_pdf_from_json.py
    python generate_pdf_from_json.py --company jsons/company.json --screening jsons/screening_results.json --output output.pdf
"""

import json
import os
import sys
import argparse
from datetime import date, datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
styles = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "Title_KYC", parent=styles["Heading1"],
    fontSize=13, spaceAfter=2, textColor=colors.black,
    fontName="Helvetica-Bold",
)
SUBTITLE = ParagraphStyle(
    "Subtitle_KYC", parent=styles["Normal"],
    fontSize=10, spaceAfter=2, textColor=colors.black,
    fontName="Helvetica-Bold",
)
H2 = ParagraphStyle(
    "H2_KYC", parent=styles["Heading2"],
    fontSize=11, spaceAfter=4, textColor=colors.HexColor("#333333"),
    fontName="Helvetica-Bold",
)
BODY = ParagraphStyle(
    "Body_KYC", parent=styles["Normal"],
    fontSize=9, leading=12, fontName="Helvetica",
)
BODY_BOLD = ParagraphStyle(
    "Body_Bold_KYC", parent=styles["Normal"],
    fontSize=9, leading=12, fontName="Helvetica-Bold",
)
SMALL = ParagraphStyle(
    "Small_KYC", parent=styles["Normal"],
    fontSize=8, leading=10, textColor=colors.grey, fontName="Helvetica",
)
CONFIDENTIAL = ParagraphStyle(
    "Confidential", parent=styles["Normal"],
    fontSize=10, textColor=colors.grey, fontName="Helvetica-Bold",
    alignment=2,  # RIGHT
)

# Table styles
TABLE_GRID = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])

LABEL_COL = TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
])

HEADER_ROW_BLACK = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
])

HEADER_ROW_GREY = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
])

SUB_HEADER_GREY = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _p(text, style=None) -> Paragraph:
    """Wrap text in a Paragraph."""
    if style is None:
        style = BODY
    return Paragraph("" if text in (None, "", "N/A") else str(text), style)


def _pb(text) -> Paragraph:
    """Wrap text in a bold Paragraph."""
    return Paragraph("" if text in (None, "", "N/A") else str(text), BODY_BOLD)


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def _today_str():
    return date.today().strftime("%d-%b-%Y")


def _footer_note(page_label: str):
    return Paragraph(f"KYC Form {page_label} / {_today_str()}", SMALL)


def _section_header_table(title: str, full_width=17 * cm):
    """Create a full-width black background section header."""
    t = Table([[Paragraph(title, ParagraphStyle(
        "sect_hdr", parent=BODY, fontName="Helvetica-Bold",
        textColor=colors.white, fontSize=9,
    ))]], colWidths=[full_width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _name_list(names):
    """Format a numbered list of names."""
    if not names:
        return ""
    return "<br/>".join(f"{i + 1}. {n}" for i, n in enumerate(names))


# ---------------------------------------------------------------------------
# Data extraction from JSONs
# ---------------------------------------------------------------------------
def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_data(company_json_path: str, screening_json_path: str) -> dict:
    """
    Extract and assemble all data needed for the KYC PDF from the two
    JSON files. The first company in company.json is treated as the primary
    client; all companies contribute screening results.
    """
    companies = load_json(company_json_path)
    if isinstance(companies, dict):
        companies = [companies]

    screening_data = load_json(screening_json_path)
    all_results = screening_data.get("screening_results", [])

    # Primary company is the first entry (has full company_profile.company_profile)
    primary = companies[0]
    primary_id = primary.get("company_number", "")
    profile = primary.get("company_profile", {}) or {}
    company_profile_block = profile.get("company_profile", {}) or {}
    persons = profile.get("management_and_control_persons", []) or []
    shareholders = profile.get("shareholders_and_members", []) or []

    # Collect ALL company IDs
    all_company_ids = [c.get("company_number", "") for c in companies]

    # Gather all persons across all companies (deduplicate by name)
    all_persons = []
    seen_names = set()
    for c in companies:
        cp = c.get("company_profile", {}) or {}
        for p in cp.get("management_and_control_persons", []) or []:
            name = p.get("full_name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                all_persons.append(p)

    # Gather all shareholders across all companies (deduplicate by name)
    all_shareholders = []
    seen_sh = set()
    for c in companies:
        cp = c.get("company_profile", {}) or {}
        for s in cp.get("shareholders_and_members", []) or []:
            name = s.get("name", "")
            if name and name not in seen_sh:
                seen_sh.add(name)
                all_shareholders.append(s)

    # Gather all beneficial owners across all companies (deduplicate)
    all_bos = []
    seen_bos = set()
    for c in companies:
        cp = c.get("company_profile", {}) or {}
        for bo in cp.get("beneficial_owners", []) or []:
            name = bo.get("full_name", "")
            if name and name not in seen_bos:
                seen_bos.add(name)
                all_bos.append(bo)

    # Gather all screening results across all company IDs
    company_results = [r for r in all_results if r.get("company_id") in all_company_ids]

    # --- PEP detection ---
    domestic_peps = []
    foreign_peps = []
    soe_entities = []
    seen_pep_names = set()
    seen_soe_names = set()

    for r in company_results:
        summary = r.get("screening_summary", {}) or {}
        name = r.get("matched_name") or r.get("search_name") or ""
        if not name:
            continue

        if summary.get("pep_flag"):
            entity_type = r.get("entity_type_hint", "")
            if entity_type == "INDIVIDUAL":
                profile_nat = (r.get("matched_profile", {}) or {}).get("nationality", "")
                if name not in seen_pep_names:
                    seen_pep_names.add(name)
                    if profile_nat and profile_nat.upper() not in ("MALAYSIA", "MALAY"):
                        foreign_peps.append(name)
                    else:
                        domestic_peps.append(name)
            elif entity_type == "CORPORATE":
                if name not in seen_soe_names:
                    seen_soe_names.add(name)
                    soe_entities.append(name)

    # --- Sanctions / adverse news ---
    sanctions_hits = list({
        r.get("matched_name") or r.get("search_name")
        for r in company_results
        if (r.get("screening_summary", {}) or {}).get("sanctions_flag")
    })
    adverse_news_hits = list({
        r.get("matched_name") or r.get("search_name")
        for r in company_results
        if (r.get("screening_summary", {}) or {}).get("adverse_news_flag")
    })

    # --- Risk rating ---
    any_flag = bool(domestic_peps or foreign_peps or sanctions_hits or adverse_news_hits)
    kyc_risk_rating = "HIGH" if any_flag else "LOW"

    # --- Client screening summary (for page 1) ---
    client_result = next(
        (r for r in company_results if r.get("role") == "CLIENT"
         and r.get("screening_summary", {}).get("computed_risk_rating")),
        None
    )
    if client_result:
        client_summary = client_result.get("screening_summary", {})
        risk_rating = client_summary.get("override_risk_rating") or client_summary.get("computed_risk_rating") or kyc_risk_rating
    else:
        risk_rating = kyc_risk_rating

    # --- Screening evidence details for each entity ---
    screening_details = []
    for r in company_results:
        if r.get("search_name"):
            screening_details.append({
                "company_id": r.get("company_id", ""),
                "search_name": r.get("search_name"),
                "role": r.get("role"),
                "entity_type": r.get("entity_type_hint"),
                "result_status": r.get("artemis_result_status"),
                "match_confidence": r.get("match_confidence"),
                "matched_name": r.get("matched_name"),
                "screening_summary": r.get("screening_summary", {}),
                "screening_evidence": r.get("screening_evidence", []),
                "narrative_conclusion": r.get("narrative_conclusion", ""),
            })

    return {
        "client_name": company_profile_block.get("company_name", "N/A"),
        "registration_no": company_profile_block.get("registration_no") or primary_id,
        "incorporation_date": company_profile_block.get("incorporation_date", ""),
        "company_type": company_profile_block.get("company_type", ""),
        "legal_form": company_profile_block.get("legal_form", ""),
        "status": company_profile_block.get("status", ""),
        "country_of_incorporation": company_profile_block.get("country_of_incorporation", ""),
        "registered_address": company_profile_block.get("registered_address", ""),
        "business_address": company_profile_block.get("business_address", ""),
        "nature_of_business": company_profile_block.get("nature_of_business", ""),
        "kyc_risk_rating": risk_rating,
        "pep_flag": bool(domestic_peps or foreign_peps),
        "pep_details": "Domestic PEP" if domestic_peps else ("Foreign PEP" if foreign_peps else "N/A"),
        "higher_risk_jurisdiction": False,
        "alert_list_flag": bool(sanctions_hits),
        "investigation_flag": False,
        "adverse_info_flag": bool(adverse_news_hits),
        "management_and_control_persons": [
            {
                "full_name": p.get("full_name"),
                "role": p.get("role"),
                "id_type": p.get("id_type"),
                "id_number": p.get("id_number"),
                "date_of_birth": p.get("date_of_birth"),
                "nationality": p.get("nationality") or p.get("country_of_residence"),
                "country_of_residence": p.get("country_of_residence"),
                "gender": p.get("gender"),
                "occupation": p.get("occupation"),
                "residential_address": p.get("residential_address"),
                "service_address": p.get("service_address"),
                "email": p.get("email"),
            }
            for p in all_persons
        ],
        "shareholders_and_members": [
            {
                "name": s.get("name"),
                "member_type": s.get("member_type"),
                "role": s.get("role"),
                "registration_no_or_id_no": s.get("registration_no_or_id_no"),
                "nationality_or_country": s.get("nationality_or_country"),
                "address": s.get("address"),
                "shares_held": s.get("shares_held"),
                "share_class": s.get("share_class"),
                "ownership_percent": s.get("ownership_percent_if_available"),
            }
            for s in all_shareholders
        ],
        "beneficial_owners": [
            {
                "full_name": bo.get("full_name"),
                "id_number": bo.get("id_number"),
                "nationality": bo.get("nationality"),
                "control_basis": bo.get("control_basis"),
                "ownership_percent": bo.get("ownership_percent_if_known"),
            }
            for bo in all_bos
        ],
        "domestic_peps": domestic_peps,
        "foreign_peps": foreign_peps,
        "soe_entities": soe_entities,
        "sanctions_hits": sanctions_hits,
        "adverse_news_hits": adverse_news_hits,
        "screening_details": screening_details,
        "all_company_ids": all_company_ids,
        "generated_date": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# PDF Generation
# ---------------------------------------------------------------------------
def generate_kyc_pdf(data: dict, output_path: str) -> str:
    """Generate the multi-page KYC Assessment Form PDF."""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    PAGE_WIDTH = A4[0] - 3 * cm  # usable width
    story = []

    # ================================================================ PAGE 1
    story.append(Paragraph("CONFIDENTIAL", CONFIDENTIAL))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Know Your Client ('KYC') Assessment Form", TITLE))
    story.append(Paragraph("(For Gazetted Activities)", SUBTITLE))
    story.append(_footer_note("Pg 1"))
    story.append(Spacer(1, 8))

    # --- Details ---
    story.append(_section_header_table("Details", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    details = Table([
        [_pb("Name of Client"), _p(data["client_name"])],
        [_pb("Registration No."), _p(data["registration_no"])],
        [_pb("Incorporation Date"), _p(data.get("incorporation_date", ""))],
        [_pb("Company Type"), _p(f'{data.get("legal_form", "")} / {data.get("company_type", "")}')],
        [_pb("Status"), _p(data.get("status", ""))],
        [_pb("Country of Incorporation"), _p(data.get("country_of_incorporation", ""))],
        [_pb("Nature of Business"), _p(data.get("nature_of_business", ""))],
        [_pb("KYC Risk Rating"), _p(data["kyc_risk_rating"])],
    ], colWidths=[6 * cm, PAGE_WIDTH - 6 * cm])
    details.setStyle(TABLE_GRID)
    details.setStyle(LABEL_COL)
    story.append(details)
    story.append(Spacer(1, 10))

    # --- Summary of Relevant Information ---
    story.append(_section_header_table("Summary of Relevant Information", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    summary_rows = [
        [_pb(""), _pb("Yes/No"), _pb("Details")],
        [_p("Politically Exposed Person ('PEP')"), _p(_yes_no(data["pep_flag"])), _p(data["pep_details"])],
        [_p("Higher Risk Jurisdiction(s)/country(ies)"), _p(_yes_no(data["higher_risk_jurisdiction"])), _p("N/A")],
        [_p("Client/BO/Director listed in alert list issued by authorities"),
         _p(_yes_no(data["alert_list_flag"])),
         _p(", ".join(data["sanctions_hits"]) or "N/A")],
        [_p("Client/BO/Director under investigation orders issued by authorities"),
         _p(_yes_no(data["investigation_flag"])), _p("N/A")],
        [_p("Adverse information about the Client/BO/Director"),
         _p(_yes_no(data["adverse_info_flag"])),
         _p(", ".join(data["adverse_news_hits"]) or "N/A")],
    ]
    summary_table = Table(summary_rows, colWidths=[9 * cm, 2.5 * cm, PAGE_WIDTH - 11.5 * cm])
    summary_table.setStyle(TABLE_GRID)
    summary_table.setStyle(HEADER_ROW_GREY)
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # --- Objective ---
    story.append(Paragraph("<b>Objective</b>", BODY_BOLD))
    story.append(Paragraph(
        "To document our KYC risk assessment and response during the client / retention stage",
        BODY,
    ))
    story.append(Spacer(1, 10))

    # --- Registered Address ---
    story.append(_section_header_table("Registered & Business Address", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    addr_table = Table([
        [_pb("Registered Address"), _p(data.get("registered_address", ""))],
        [_pb("Business Address"), _p(data.get("business_address", ""))],
    ], colWidths=[6 * cm, PAGE_WIDTH - 6 * cm])
    addr_table.setStyle(TABLE_GRID)
    addr_table.setStyle(LABEL_COL)
    story.append(addr_table)

    story.append(PageBreak())

    # ================================================================ PAGE 2
    story.append(Paragraph("KYC Assessment Form (continued)", SUBTITLE))
    story.append(Paragraph("(For Gazetted Activities)", SMALL))
    story.append(Paragraph("PART A - Client Due Diligence", SUBTITLE))
    story.append(_footer_note("Pg 2"))
    story.append(Spacer(1, 8))

    # --- SECTION 2 - Management & Control Persons ---
    story.append(_section_header_table("SECTION 2 - Management & Control Persons", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    persons_rows = [[_pb("Full Name"), _pb("Role"), _pb("ID Number"),
                     _pb("Nationality / Residence")]]
    for p in data["management_and_control_persons"]:
        persons_rows.append([
            _p(p["full_name"]),
            _p(p["role"]),
            _p(p["id_number"]),
            _p(p.get("nationality") or p.get("country_of_residence") or ""),
        ])
    persons_table = Table(persons_rows, colWidths=[5.5 * cm, 3 * cm, 4 * cm, PAGE_WIDTH - 12.5 * cm])
    persons_table.setStyle(TABLE_GRID)
    persons_table.setStyle(HEADER_ROW_BLACK)
    story.append(persons_table)
    story.append(Spacer(1, 10))

    # --- SECTION 3 - Shareholders & Members ---
    story.append(_section_header_table("SECTION 3 - Shareholders & Members", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    sh_rows = [[_pb("Name"), _pb("Type"), _pb("Reg./ID No."),
                _pb("Shares Held"), _pb("Share Class"), _pb("Ownership %")]]
    for s in data["shareholders_and_members"]:
        sh_rows.append([
            _p(s["name"]),
            _p(s["member_type"]),
            _p(s["registration_no_or_id_no"]),
            _p(str(s.get("shares_held", "")) if s.get("shares_held") else ""),
            _p(s.get("share_class", "")),
            _p(f'{s.get("ownership_percent", "")}%' if s.get("ownership_percent") else ""),
        ])
    sh_table = Table(sh_rows, colWidths=[5 * cm, 2.5 * cm, 3.5 * cm, 2.5 * cm, 2 * cm, PAGE_WIDTH - 15.5 * cm])
    sh_table.setStyle(TABLE_GRID)
    sh_table.setStyle(HEADER_ROW_BLACK)
    story.append(sh_table)
    story.append(Spacer(1, 10))

    # --- Beneficial Owners ---
    if data.get("beneficial_owners"):
        story.append(_section_header_table("Beneficial Owner(s)", PAGE_WIDTH))
        story.append(Spacer(1, 2))
        bo_rows = [[_pb("Full Name"), _pb("ID Number"), _pb("Nationality"),
                     _pb("Control Basis"), _pb("Ownership %")]]
        for bo in data["beneficial_owners"]:
            bo_rows.append([
                _p(bo["full_name"]),
                _p(bo.get("id_number", "")),
                _p(bo.get("nationality", "")),
                _p(bo.get("control_basis", "")),
                _p(f'{bo.get("ownership_percent", "")}%' if bo.get("ownership_percent") else ""),
            ])
        bo_table = Table(bo_rows, colWidths=[5 * cm, 3.5 * cm, 3 * cm, 3.5 * cm, PAGE_WIDTH - 15 * cm])
        bo_table.setStyle(TABLE_GRID)
        bo_table.setStyle(HEADER_ROW_BLACK)
        story.append(bo_table)

    story.append(PageBreak())

    # ================================================================ PAGE 3
    story.append(Paragraph("KYC Assessment Form (continued)", SUBTITLE))
    story.append(Paragraph("(For Gazetted Activities)", SMALL))
    story.append(Paragraph("PART A - Client Due Diligence", SUBTITLE))
    story.append(_footer_note("Pg 3"))
    story.append(Spacer(1, 8))

    # --- SECTION 4 - Client Risk Profiling ---
    story.append(_section_header_table("SECTION 4 - Client Risk Profiling", PAGE_WIDTH))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "Based on the Artemis screening, is the client, BO and/or Director(s) classified as "
        "PEP(s) or relatives or close associates ('RCA') of PEP?",
        BODY,
    ))
    story.append(Spacer(1, 4))

    pep_rows = [
        [_pb("Risk Category"), _pb("Yes/No"), _pb("Name of the PEP(s)")],
        [_p("Foreign PEP"), _p(_yes_no(bool(data["foreign_peps"]))),
         _p(_name_list(data["foreign_peps"]) or "")],
        [_p("Domestic PEP"), _p(_yes_no(bool(data["domestic_peps"]))),
         _p(_name_list(data["domestic_peps"]) or "")],
        [_p("RCA of Foreign PEP"), _p("No"), _p("")],
        [_p("RCA of Domestic PEP"), _p("No"), _p("")],
        [_p("Persons who are or have been entrusted with a prominent function by an "
            "international organisation which refers to members of senior management"),
         _p("No"), _p("")],
        [_p("State-owned Enterprise / state-invested entity"),
         _p(_yes_no(bool(data["soe_entities"]))),
         _p(_name_list(data["soe_entities"]) or "")],
        [_p("Does the client, BO or Directors appear on the sanctions lists?"),
         _p(_yes_no(bool(data["sanctions_hits"]))),
         _p(_name_list(data["sanctions_hits"]) or "")],
    ]
    pep_table = Table(pep_rows, colWidths=[7 * cm, 2 * cm, PAGE_WIDTH - 9 * cm])
    pep_table.setStyle(TABLE_GRID)
    pep_table.setStyle(HEADER_ROW_BLACK)
    story.append(pep_table)
    story.append(Spacer(1, 10))

    # --- Section 4A - Client Risk ---
    s4a_rows = [
        [_pb("SECTION 4A - Client Risk"), _pb("Yes/No/Details")],
        [_p("Business structure description"), _p("Simple")],
        [_p("Investigation orders/alert lists"), _p(_yes_no(data["investigation_flag"]))],
        [_p("Unusual business relationship requirements"), _p("No")],
        [_p("Adverse public domain info, high-risk industry involvement"), _p(_yes_no(data["adverse_info_flag"]))],
    ]
    s4a_table = Table(s4a_rows, colWidths=[12 * cm, PAGE_WIDTH - 12 * cm])
    s4a_table.setStyle(TABLE_GRID)
    s4a_table.setStyle(HEADER_ROW_GREY)
    story.append(s4a_table)
    story.append(Spacer(1, 6))

    # --- Section 4B - Geographical Risk ---
    s4b_rows = [
        [_pb("Section 4B - Geographical Risk"), _pb("Yes/No/Details")],
        [_p("Client residency/connections to high-risk countries"), _p("No")],
        [_p("BO/Director/Shareholder connections to sanctioned or high-risk jurisdictions/offshore tax havens"), _p("No")],
    ]
    s4b_table = Table(s4b_rows, colWidths=[12 * cm, PAGE_WIDTH - 12 * cm])
    s4b_table.setStyle(TABLE_GRID)
    s4b_table.setStyle(HEADER_ROW_GREY)
    story.append(s4b_table)
    story.append(Spacer(1, 6))

    # --- Section 4C - Product/Service Risk ---
    s4c_rows = [
        [_pb("Section 4C - Product/Service Risk"), _pb("Yes/No/Details")],
        [_p("Cross-border services"), _p("No")],
        [_p("Complex structures obscuring ownership"), _p("No")],
    ]
    s4c_table = Table(s4c_rows, colWidths=[12 * cm, PAGE_WIDTH - 12 * cm])
    s4c_table.setStyle(TABLE_GRID)
    s4c_table.setStyle(HEADER_ROW_GREY)
    story.append(s4c_table)
    story.append(Spacer(1, 6))

    # --- Section 4D - Transaction Risk ---
    s4d_rows = [
        [_pb("Section 4D - Transaction and Delivery Channel Risk"), _pb("Yes/No/Details")],
        [_p("Non face-to-face business relationships"), _p("No")],
    ]
    s4d_table = Table(s4d_rows, colWidths=[12 * cm, PAGE_WIDTH - 12 * cm])
    s4d_table.setStyle(TABLE_GRID)
    s4d_table.setStyle(HEADER_ROW_GREY)
    story.append(s4d_table)
    story.append(Spacer(1, 6))

    # --- Section 4E - Others ---
    s4e_rows = [
        [_pb("Section 4E - Others"), _pb("Yes/No/Details")],
        [_p("Any other high-risk indicators"), _p("No")],
    ]
    s4e_table = Table(s4e_rows, colWidths=[12 * cm, PAGE_WIDTH - 12 * cm])
    s4e_table.setStyle(TABLE_GRID)
    s4e_table.setStyle(HEADER_ROW_GREY)
    story.append(s4e_table)

    story.append(PageBreak())

    # ================================================================ PAGE 4
    story.append(Paragraph("KYC Assessment Form (continued)", SUBTITLE))
    story.append(Paragraph("(For Gazetted Activities)", SMALL))
    story.append(Paragraph("PART A - Client Due Diligence", SUBTITLE))
    story.append(_footer_note("Pg 4"))
    story.append(Spacer(1, 8))

    # --- SECTION 5 - KYC Risk Rating ---
    story.append(_section_header_table("SECTION 5 - KYC Risk Rating", PAGE_WIDTH))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Based on Section 4 of this form, the KYC Risk Rating by the engagement team is:",
        BODY,
    ))
    story.append(Spacer(1, 4))
    risk_row = Table([
        [_pb("KYC Risk Rating"), _p(data["kyc_risk_rating"])],
    ], colWidths=[6 * cm, PAGE_WIDTH - 6 * cm])
    risk_row.setStyle(TABLE_GRID)
    risk_row.setStyle(LABEL_COL)
    story.append(risk_row)
    story.append(Spacer(1, 6))

    if data["kyc_risk_rating"] == "HIGH" or data["pep_flag"]:
        story.append(Paragraph(
            "If your KYC Risk Rating is High or if there are PEPs/RCA of PEPs identified, "
            "please complete the Enhanced Client Due Diligence under Part B.",
            BODY,
        ))
    story.append(Spacer(1, 10))

    story.append(PageBreak())

    # ================================================================ PAGE 5+
    # Part B - Enhanced Due Diligence (if HIGH risk or PEP)
    story.append(Paragraph("KYC Assessment Form (continued)", SUBTITLE))
    story.append(Paragraph("(For Gazetted Activities)", SMALL))
    story.append(Paragraph("Part B - Enhanced Due Diligence", SUBTITLE))
    story.append(_footer_note("Pg 5"))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Please complete this Part B for clients with High-Risk Ratings or "
        "if there are PEPs/RCA of PEPs identified.",
        BODY,
    ))
    story.append(Spacer(1, 6))

    # Section: Additional information
    story.append(_section_header_table(
        "1. Obtain additional information on the client and Beneficial Owner(s) "
        "(i.e. volume of assets and other information from commercial or public databases)",
        PAGE_WIDTH,
    ))
    story.append(Spacer(1, 2))

    edd_rows = [
        [_pb("Client"), _p(f'{data["client_name"]} ({data["registration_no"]})')],
        [_pb("Nature of Business"), _p(data.get("nature_of_business", "N/A"))],
        [_pb("Country of Incorporation"), _p(data.get("country_of_incorporation", ""))],
        [_pb("Beneficial Owner(s)"), _p(
            ", ".join(bo["full_name"] for bo in data.get("beneficial_owners", []) if bo.get("full_name")) or "Refer Appendix"
        )],
    ]
    edd_table = Table(edd_rows, colWidths=[6 * cm, PAGE_WIDTH - 6 * cm])
    edd_table.setStyle(TABLE_GRID)
    edd_table.setStyle(LABEL_COL)
    story.append(edd_table)
    story.append(Spacer(1, 10))

    # Section: Source of wealth
    story.append(_section_header_table(
        "2. What is the source of wealth or source of funds for the following individuals? "
        "In the case of PEPs, both sources must be obtained.",
        PAGE_WIDTH,
    ))
    story.append(Spacer(1, 2))

    pep_source_rows = [
        [_pb("Beneficial Owner"), _p("Refer Appendix")],
        [_pb("PEP(s)"), _p("Professional corporate roles, compensation, equity")],
    ]
    pep_source_table = Table(pep_source_rows, colWidths=[6 * cm, PAGE_WIDTH - 6 * cm])
    pep_source_table.setStyle(TABLE_GRID)
    pep_source_table.setStyle(LABEL_COL)
    story.append(pep_source_table)

    story.append(PageBreak())

    # ================================================================ APPENDIX PAGES
    # Screening Results Appendix
    story.append(Paragraph("APPENDIX - Screening Results Summary", TITLE))
    story.append(_footer_note("Appendix"))
    story.append(Spacer(1, 8))

    # Group screening results by company_id from data
    results_by_company = {}
    for r in data.get("screening_details", []):
        cid = r.get("company_id", "Unknown")
        if cid not in results_by_company:
            results_by_company[cid] = []
        results_by_company[cid].append(r)

    # If grouping failed, just list all screening details
    if not results_by_company:
        results_by_company = {"All": data.get("screening_details", [])}

    for company_id, results in results_by_company.items():
        story.append(Paragraph(f"Company: {company_id}", H2))
        story.append(Spacer(1, 4))

        for r in results:
            search_name = r.get("search_name", "N/A")
            role = r.get("role", "")
            result_status = r.get("result_status", "")
            confidence = r.get("match_confidence", "")
            summary = r.get("screening_summary", {}) or {}
            evidence_list = r.get("screening_evidence", [])
            narrative = r.get("narrative_conclusion", "")

            # Entity header
            entity_header = Table([
                [_pb(f"{search_name}"), _p(f"Role: {role}"), _p(f"Status: {result_status}")],
            ], colWidths=[7 * cm, 5 * cm, PAGE_WIDTH - 12 * cm])
            entity_header.setStyle(TABLE_GRID)
            entity_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f0f0")),
            ]))
            story.append(entity_header)

            # Flags row
            pep = "Yes" if summary.get("pep_flag") else "No"
            sanc = "Yes" if summary.get("sanctions_flag") else "No"
            adv = "Yes" if summary.get("adverse_news_flag") else "No"
            no_hit = "Yes" if summary.get("no_hit_flag") else "No"

            flags_row = Table([
                [_pb("PEP"), _p(pep), _pb("Sanctions"), _p(sanc),
                 _pb("Adverse News"), _p(adv), _pb("No Hit"), _p(no_hit)],
            ], colWidths=[2 * cm, 1 * cm, 2.5 * cm, 1 * cm, 3 * cm, 1 * cm, 2 * cm, PAGE_WIDTH - 12.5 * cm])
            flags_row.setStyle(TABLE_GRID)
            story.append(flags_row)

            # Confidence & officer
            if confidence:
                officer = summary.get("screening_officer_name", "")
                updated = summary.get("summary_last_updated", "")
                info_row = Table([
                    [_pb("Confidence"), _p(confidence), _pb("Officer"), _p(officer), _pb("Updated"), _p(str(updated)[:10] if updated else "")],
                ], colWidths=[2.5 * cm, 2.5 * cm, 2 * cm, 4 * cm, 2 * cm, PAGE_WIDTH - 13 * cm])
                info_row.setStyle(TABLE_GRID)
                story.append(info_row)

            # Screening evidence
            if evidence_list:
                ev_rows = [[_pb("Source"), _pb("Match"), _pb("Categories"),
                            _pb("Countries"), _pb("Strength"), _pb("Comments")]]
                for ev in evidence_list:
                    ev_rows.append([
                        _p(ev.get("source_list", "")),
                        _p(ev.get("matched_indicator", "")),
                        _p(", ".join(ev.get("categories", []))),
                        _p(", ".join(ev.get("countries", []))),
                        _p(ev.get("match_strength", "")),
                        _p(ev.get("comments", "")),
                    ])
                ev_table = Table(ev_rows, colWidths=[2.2 * cm, 1.5 * cm, 2 * cm, 3.5 * cm, 2 * cm, PAGE_WIDTH - 11.2 * cm])
                ev_table.setStyle(TABLE_GRID)
                ev_table.setStyle(HEADER_ROW_GREY)
                story.append(ev_table)

            # Narrative
            if narrative:
                story.append(Spacer(1, 2))
                story.append(Paragraph(f"<i>Conclusion: {narrative}</i>", BODY))

            story.append(Spacer(1, 8))

    # ================================================================ BUILD
    doc.build(story)
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate KYC Assessment Form PDF from company.json and screening_results.json"
    )
    parser.add_argument(
        "--company", "-c",
        default="./jsons/company.json",
        help="Path to company.json (default: ./jsons/company.json)",
    )
    parser.add_argument(
        "--screening", "-s",
        default="./jsons/screening_results.json",
        help="Path to screening_results.json (default: ./jsons/screening_results.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default="./uploads/kyc_report.pdf",
        help="Output PDF path (default: ./uploads/kyc_report.pdf)",
    )
    args = parser.parse_args()

    print(f"Loading company data from: {args.company}")
    print(f"Loading screening data from: {args.screening}")

    data = extract_data(args.company, args.screening)

    # print(f"Client: {data['client_name']}")
    # print(f"Risk Rating: {data['kyc_risk_rating']}")
    # print(f"Domestic PEPs: {data['domestic_peps']}")
    # print(f"Foreign PEPs: {data['foreign_peps']}")
    # print(f"SOE Entities: {data['soe_entities']}")
    # print(f"Sanctions Hits: {data['sanctions_hits']}")
    # print(f"Adverse News: {data['adverse_news_hits']}")
    # print(f"Total persons: {len(data['management_and_control_persons'])}")
    # print(f"Total shareholders: {len(data['shareholders_and_members'])}")
    # print(f"Total beneficial owners: {len(data['beneficial_owners'])}")
    # print()

    output = generate_kyc_pdf(data, args.output)
    print(f"[OK] PDF generated successfully: {os.path.abspath(output)}")


if __name__ == "__main__":
    main()
