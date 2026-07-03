import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=13, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceAfter=4, textColor=colors.HexColor("#333333"))
BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12)
SMALL = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.grey)

TABLE_GRID = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])

LABEL_COL = TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
])


def _p(text) -> Paragraph:
    return Paragraph("" if text in (None, "") else str(text), BODY)


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def _today():
    from datetime import date
    return date.today().strftime("%d-%b-%Y")


def _footer_note(page_label: str):
    return Paragraph(f"KYC Form {page_label} / {_today()}", SMALL)


def generate_kyc_pdf(data: dict, output_path: str) -> str:
    """Render the KYC Assessment Form PDF from an already-assembled data dict
    (see build_kyc_data.build_kyc_input). Purely formatting -- every value
    placed on the page comes verbatim from `data`."""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    story = []

    # ---------------------------------------------------------------- Page 1
    story.append(Paragraph("KYC Assessment Form", H1))
    story.append(Paragraph("(For Gazetted Activities)", SMALL))
    story.append(_footer_note("Pg 1"))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Details", H2))
    details_table = Table([
        ["Name of Client", _p(data["client_name"])],
        ["Year Ending (if applicable)", _p(data["year_ending"])],
        ["Nature of Service / Purpose of transaction", _p(data["nature_of_service"])],
        ["KYC Risk Rating", _p(data["kyc_risk_rating"])],
    ], colWidths=[6 * cm, 11 * cm])
    details_table.setStyle(TABLE_GRID)
    details_table.setStyle(LABEL_COL)
    story.append(details_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary of Relevant Information", H2))
    summary_rows = [
        ["", "Yes/No", "Details"],
        ["Politically Exposed Person ('PEP')", _yes_no(data["pep_flag"]), _p(data["pep_details"])],
        ["Higher Risk Jurisdiction(s)/country(ies)", _yes_no(data["higher_risk_jurisdiction"]), "N/A"],
        ["Client/BO/Director listed in alert list issued by authorities", _yes_no(data["alert_list_flag"]),
         _p(", ".join(data["sanctions_hits"]) or "N/A")],
        ["Client/BO/Director under investigation orders issued by authorities",
         _yes_no(data["investigation_flag"]), "N/A"],
        ["Adverse information about the Client/BO/Director", _yes_no(data["adverse_info_flag"]),
         _p(", ".join(data["adverse_news_hits"]) or "N/A")],
    ]
    summary_table = Table(summary_rows, colWidths=[9 * cm, 2.5 * cm, 5.5 * cm])
    summary_table.setStyle(TABLE_GRID)
    summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Objective", H2))
    story.append(Paragraph(
        "To document our KYC risk assessment and response during the client / retention stage",
        BODY,
    ))
    story.append(Spacer(1, 10))

    approvals = data["approvals"]
    story.append(Paragraph("Completion of KYC Assessment", H2))
    completion_table = Table([
        ["Tasks", "Name", "Designation", "Signature", "Dates"],
        ["Prepared by", _p(approvals["prepared_by"]["name"]), _p(approvals["prepared_by"]["designation"]), "", _p(approvals["prepared_by"]["date"])],
        ["Reviewed by", _p(approvals["reviewed_by"]["name"]), _p(approvals["reviewed_by"]["designation"]), "", _p(approvals["reviewed_by"]["date"])],
    ], colWidths=[3 * cm, 4.5 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm])
    completion_table.setStyle(TABLE_GRID)
    completion_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                                           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(completion_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Approval", H2))
    approval_table = Table([
        ["Reviewed by Engagement", "Approved by", ""],
        [f"Name: {approvals['reviewed_by']['name'] or 'N/A'}",
         f"Name: {approvals['approved_by']['name'] or 'N/A'}", ""],
        [f"Designation: {approvals['reviewed_by']['designation'] or 'N/A'}",
         f"Designation: {approvals['approved_by']['designation'] or 'N/A'}", ""],
        [f"Date: {approvals['reviewed_by']['date'] or 'N/A'}",
         f"Date: {approvals['approved_by']['date'] or 'N/A'}", ""],
    ], colWidths=[7.5 * cm, 7.5 * cm, 2 * cm])
    approval_table.setStyle(TABLE_GRID)
    story.append(approval_table)

    story.append(PageBreak())

    # ---------------------------------------------------------------- Page 2
    story.append(Paragraph("KYC Assessment Form (continued)", H1))
    story.append(Paragraph("PART A - Client Due Diligence", SMALL))
    story.append(_footer_note("Pg 2"))
    story.append(Spacer(1, 10))

    eng = data["engagement"]
    story.append(Paragraph("SECTION 1 - Engagement Information", H2))
    section1 = Table([
        ["Type of client (IND / LP / LA / CSC)", _p(eng["type_of_client"])],
        ["Type of engagement (Recurring/Non-recurring)", _p(eng["type_of_engagement"])],
        ["Nature of Service", _p(eng["nature_of_service"])],
        ["Proposed services", _p(eng["proposed_services"])],
        ["Which office will accept/retain the client?", _p(eng["office"])],
        ["Classification of engagement as a Gazetted Activity", _p(eng["gazetted_activity"])],
    ], colWidths=[8 * cm, 9 * cm])
    section1.setStyle(TABLE_GRID)
    section1.setStyle(LABEL_COL)
    story.append(section1)
    story.append(Spacer(1, 10))

    story.append(Paragraph("SECTION 2 - Information of the Client", H2))
    persons_rows = [["Full Name", "Role", "ID Number", "Nationality/Residence"]]
    for p in data["management_and_control_persons"]:
        persons_rows.append([_p(p["full_name"]), _p(p["role"]), _p(p["id_number"]), _p(p["nationality"])])
    persons_table = Table(persons_rows, colWidths=[5.5 * cm, 3.5 * cm, 4 * cm, 4 * cm])
    persons_table.setStyle(TABLE_GRID)
    persons_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(Paragraph(f"Business registration no.: {data['registration_no']}", BODY))
    story.append(Paragraph(f"Address of principal place of business: {data['principal_place_of_business']}", BODY))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Senior management names:", BODY))
    story.append(persons_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("SECTION 3 - Beneficial Owner(s)", H2))
    shareholder_rows = [["Name", "Type", "Registration/ID No.", "Shares Held"]]
    for s in data["shareholders_and_members"]:
        shareholder_rows.append([_p(s["name"]), _p(s["member_type"]), _p(s["registration_no_or_id_no"]), _p(s["shares_held"])])
    shareholder_table = Table(shareholder_rows, colWidths=[6 * cm, 3 * cm, 4.5 * cm, 3.5 * cm])
    shareholder_table.setStyle(TABLE_GRID)
    shareholder_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(shareholder_table)

    story.append(PageBreak())

    # ---------------------------------------------------------------- Page 3
    story.append(Paragraph("KYC Assessment Form (continued)", H1))
    story.append(Paragraph("PART A - Client Due Diligence", SMALL))
    story.append(_footer_note("Pg 3"))
    story.append(Spacer(1, 10))

    story.append(Paragraph("SECTION 4 - Client Risk Profiling", H2))
    story.append(Paragraph(
        "Based on the Artemis screening, is the client, BO and/or Director(s) classified as "
        "PEP(s) or relatives or close associates ('RCA') of PEP?", BODY,
    ))
    story.append(Spacer(1, 4))

    def name_list(names):
        return "; ".join(f"{i+1}. {n}" for i, n in enumerate(names)) if names else "N/A"

    pep_rows = [
        ["Risk Category", "Yes/No", "Name(s)"],
        ["Foreign PEP", _yes_no(bool(data["foreign_peps"])), _p(name_list(data["foreign_peps"]))],
        ["Domestic PEP", _yes_no(bool(data["domestic_peps"])), _p(name_list(data["domestic_peps"]))],
        ["State-owned Enterprise / state-invested entity", _yes_no(bool(data["soe_entities"])),
         _p(name_list(data["soe_entities"]))],
        ["Does the client, BO or Directors appear on the sanctions lists?",
         _yes_no(bool(data["sanctions_hits"])), _p(name_list(data["sanctions_hits"]))],
    ]
    pep_table = Table(pep_rows, colWidths=[7 * cm, 2 * cm, 8 * cm])
    pep_table.setStyle(TABLE_GRID)
    pep_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.append(pep_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("SECTION 5 - KYC Risk Rating", H2))
    story.append(Paragraph(
        f"Based on Section 4 of this form, the KYC Risk Rating by the engagement team is "
        f"<b>{data['kyc_risk_rating']}</b>.", BODY,
    ))
    if data["kyc_risk_rating"] == "HIGH" or data["pep_flag"]:
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "If your KYC Risk Rating is High or if there are PEPs/RCA of PEPs identified, "
            "please complete the Enhanced Client Due Diligence under Part B.", BODY,
        ))

    doc.build(story)
    return output_path
