"""
PDF Service — generates a professional interview report PDF using ReportLab.

Pages:
  1. Cover page: title, candidate info, date, global score (color-coded)
  2. Competency summary table (radar-style table, no matplotlib)
  3+. Per-domain detail sections
  Appendix: Annotated transcript
"""
import io
import logging
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = A4

# ──────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ──────────────────────────────────────────────────────────────────────────────

def score_color(score: float) -> colors.Color:
    """Green ≥7, amber 4-6, red <4."""
    if score >= 7:
        return colors.HexColor("#22c55e")
    elif score >= 4:
        return colors.HexColor("#f59e0b")
    return colors.HexColor("#ef4444")

def score_color_hex(score: float) -> str:
    if score >= 7:
        return "#22c55e"
    elif score >= 4:
        return "#f59e0b"
    return "#ef4444"

def score_bg_hex(score: float) -> str:
    if score >= 7:
        return "#dcfce7"
    elif score >= 4:
        return "#fef3c7"
    return "#fee2e2"

# ──────────────────────────────────────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────────────────────────────────────

def _build_styles():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name="CoverTitle",
        fontSize=28,
        leading=34,
        alignment=TA_CENTER,
        spaceAfter=6*mm,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="CoverSubtitle",
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=4*mm,
        textColor=colors.HexColor("#64748b"),
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        fontSize=16,
        leading=20,
        spaceBefore=8*mm,
        spaceAfter=4*mm,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="SubSection",
        fontSize=12,
        leading=16,
        spaceBefore=4*mm,
        spaceAfter=2*mm,
        textColor=colors.HexColor("#334155"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BodyText2",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="SmallGray",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#94a3b8"),
    ))
    return styles


# ──────────────────────────────────────────────────────────────────────────────
# Score bar drawing
# ──────────────────────────────────────────────────────────────────────────────

def _score_bar(score: float, max_width: float = 120) -> Drawing:
    """Create a horizontal score bar."""
    d = Drawing(max_width + 40, 14)
    # Background bar
    d.add(Rect(0, 2, max_width, 10, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None))
    # Filled bar
    fill_width = max(1, (score / 10.0) * max_width)
    d.add(Rect(0, 2, fill_width, 10, fillColor=score_color(score), strokeColor=None))
    # Score text
    d.add(String(max_width + 4, 3, f"{score:.1f}", fontSize=9, fillColor=colors.HexColor("#334155")))
    return d


# ══════════════════════════════════════════════════════════════════════════════
# Main PDF builder
# ══════════════════════════════════════════════════════════════════════════════

def generate_report_pdf(report_data: dict, session_id: str) -> bytes:
    """Generate a professional PDF report and return the bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=18*mm,
        rightMargin=18*mm,
    )
    
    styles = _build_styles()
    story = []
    
    global_score = report_data.get("global_score", 0.0)
    breakdown = report_data.get("competency_breakdown", {})
    strengths = report_data.get("strengths", [])
    areas = report_data.get("areas_for_improvement", [])
    action_plan = report_data.get("action_plan", [])
    annotations = report_data.get("exchange_annotations", [])
    summary = report_data.get("session_summary", "")
    
    # ── PAGE 1: Cover ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("InterviewAI", styles["CoverTitle"]))
    story.append(Paragraph("Interview Performance Report", styles["CoverSubtitle"]))
    story.append(Spacer(1, 8*mm))
    
    # Global score — big coloured display
    sc = score_color_hex(global_score)
    story.append(Paragraph(
        f'<font size="48" color="{sc}"><b>{global_score:.1f}</b></font>'
        f'<font size="18" color="#94a3b8"> / 10</font>',
        ParagraphStyle("ScoreBig", alignment=TA_CENTER, spaceBefore=4*mm, spaceAfter=2*mm)
    ))
    
    label = "Excellent" if global_score >= 8 else "Good" if global_score >= 6 else "Needs Improvement" if global_score >= 4 else "Below Expectations"
    story.append(Paragraph(
        f'<font size="14" color="{sc}"><b>{label}</b></font>',
        ParagraphStyle("ScoreLabel", alignment=TA_CENTER, spaceAfter=10*mm)
    ))
    
    story.append(HRFlowable(width="80%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceBefore=4*mm, spaceAfter=4*mm))
    
    # Date and session info
    story.append(Paragraph(
        f'<font color="#64748b">Date: {datetime.utcnow().strftime("%B %d, %Y")}</font>',
        ParagraphStyle("CoverMeta", alignment=TA_CENTER, fontSize=11, spaceAfter=2*mm)
    ))
    story.append(Paragraph(
        f'<font color="#94a3b8">Session ID: {session_id[:8]}...</font>',
        styles["SmallGray"]
    ))
    
    story.append(PageBreak())
    
    # ── PAGE 2: Competency Summary ────────────────────────────────────────────
    story.append(Paragraph("Competency Summary", styles["SectionTitle"]))
    
    if breakdown:
        table_data = [["Domain", "Score", "Questions", "Visual", "Assessment"]]
        for domain, data in breakdown.items():
            s = data.get("score", 0)
            assessment = "Strong" if s >= 7 else "Adequate" if s >= 4 else "Weak"
            table_data.append([
                domain,
                f"{s:.1f}/10",
                str(data.get("nb_questions", 0)),
                _score_bar(s),
                assessment,
            ])
        
        t = Table(table_data, colWidths=[80, 50, 55, 170, 60])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    
    story.append(Spacer(1, 6*mm))
    
    # Strengths & Areas for improvement side by side
    story.append(Paragraph("Key Strengths", styles["SubSection"]))
    for s in strengths:
        story.append(Paragraph(f'<font color="#22c55e">✓</font>  {s}', styles["BodyText2"]))
        story.append(Spacer(1, 1*mm))
    
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Areas for Improvement", styles["SubSection"]))
    for a in areas:
        story.append(Paragraph(f'<font color="#f59e0b">▲</font>  {a}', styles["BodyText2"]))
        story.append(Spacer(1, 1*mm))
    
    story.append(PageBreak())
    
    # ── PAGE 3: Narrative Summary ─────────────────────────────────────────────
    story.append(Paragraph("Interview Summary", styles["SectionTitle"]))
    if summary:
        story.append(Paragraph(summary, styles["BodyText2"]))
    story.append(Spacer(1, 6*mm))
    
    # ── Per-domain detail ─────────────────────────────────────────────────────
    story.append(Paragraph("Domain Details", styles["SectionTitle"]))
    for domain, data in breakdown.items():
        s = data.get("score", 0)
        sc_hex = score_color_hex(s)
        story.append(Paragraph(
            f'{domain}  <font color="{sc_hex}" size="12"><b>{s:.1f}/10</b></font>',
            styles["SubSection"]
        ))
        story.append(Paragraph(data.get("feedback", "No specific feedback."), styles["BodyText2"]))
        story.append(Spacer(1, 3*mm))
    
    story.append(PageBreak())
    
    # ── Action Plan ───────────────────────────────────────────────────────────
    story.append(Paragraph("Action Plan", styles["SectionTitle"]))
    story.append(Paragraph(
        "Based on your performance, here are specific steps to improve:",
        styles["BodyText2"]
    ))
    story.append(Spacer(1, 3*mm))
    
    for i, step_data in enumerate(action_plan, 1):
        if isinstance(step_data, dict):
            step = step_data.get("step", "")
            resources = step_data.get("resources", "")
            timeframe = step_data.get("timeframe", "")
        else:
            step = str(step_data)
            resources = ""
            timeframe = ""
        
        story.append(Paragraph(f'<b>Step {i}:</b> {step}', styles["BodyText2"]))
        if resources:
            story.append(Paragraph(
                f'<font color="#6366f1">📚 Resources:</font> {resources}',
                ParagraphStyle("Resource", fontSize=9, leading=12, leftIndent=12, textColor=colors.HexColor("#475569"))
            ))
        if timeframe:
            story.append(Paragraph(
                f'<font color="#64748b">⏱ Timeframe:</font> {timeframe}',
                ParagraphStyle("Timeframe", fontSize=9, leading=12, leftIndent=12, textColor=colors.HexColor("#64748b"))
            ))
        story.append(Spacer(1, 3*mm))
    
    story.append(PageBreak())
    
    # ── Appendix: Annotated Transcript ────────────────────────────────────────
    story.append(Paragraph("Appendix: Annotated Transcript", styles["SectionTitle"]))
    
    for i, ann in enumerate(annotations, 1):
        q = ann.get("question", "")[:200]
        a = ann.get("answer_excerpt", "")[:200]
        s = ann.get("score", 0)
        fb = ann.get("key_feedback", "")
        sc_hex = score_color_hex(s)
        
        story.append(Paragraph(
            f'<b>Q{i}:</b> {q}',
            ParagraphStyle("QText", fontSize=10, leading=13, textColor=colors.HexColor("#1e293b"), spaceBefore=4*mm)
        ))
        story.append(Paragraph(
            f'<i>Answer:</i> {a}{"..." if len(a) >= 200 else ""}',
            ParagraphStyle("AText", fontSize=9, leading=12, textColor=colors.HexColor("#475569"), leftIndent=8)
        ))
        story.append(Paragraph(
            f'<font color="{sc_hex}"><b>Score: {s}/10</b></font>  —  {fb}',
            ParagraphStyle("FBText", fontSize=9, leading=12, textColor=colors.HexColor("#334155"), leftIndent=8, spaceBefore=1*mm)
        ))
        
        # Tips
        tips = ann.get("tips", [])
        for tip in tips[:2]:
            story.append(Paragraph(
                f'<font color="#f59e0b">💡</font> {tip}',
                ParagraphStyle("TipText", fontSize=8, leading=11, leftIndent=16, textColor=colors.HexColor("#64748b"))
            ))
        
        story.append(HRFlowable(width="100%", thickness=0.3, color=colors.HexColor("#e2e8f0"), spaceBefore=2*mm, spaceAfter=1*mm))
    
    # Build PDF
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    
    logger.info("PDF generated: %d bytes for session %s", len(pdf_bytes), session_id)
    return pdf_bytes
