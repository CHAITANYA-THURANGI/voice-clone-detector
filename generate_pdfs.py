"""
Markdown to PDF Converter for VoiceShield AI Documentation.
Converts markdown files into high-quality, professionally formatted PDF documents.
"""

import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

def clean_md_inline(text):
    """Clean markdown inline formatting for ReportLab Paragraphs."""
    # Convert markdown links [text](url) -> <u>text</u>
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'<u>\1</u>', text)
    # Convert bold **text** or __text__ -> <b>text</b>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
    # Convert italic *text* or _text_ -> <i>text</i>
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    # Convert inline code `code` -> <font name="Courier" color="#0284C7">code</font>
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#0369A1"><b>\1</b></font>', text)
    # Escape lone ampersands if not XML entities
    text = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', text)
    return text

def parse_markdown_to_story(md_text, styles):
    """Parses markdown lines and returns ReportLab Flowables."""
    story = []
    lines = md_text.split('\n')
    
    in_code_block = False
    code_lines = []
    
    in_table = False
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        
        # Handle code blocks
        if stripped.startswith('```'):
            if in_code_block:
                code_content = "\n".join(code_lines)
                pre = Preformatted(code_content, styles['CodeStyle'])
                story.append(pre)
                story.append(Spacer(1, 8))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue
            
        if in_code_block:
            code_lines.append(line)
            continue
            
        # Handle tables
        if stripped.startswith('|') and stripped.endswith('|'):
            # Table separator line e.g. | :--- | :--- |
            if re.match(r'^\|(\s*:?-+:?\s*\|)+$', stripped):
                continue
            cells = [c.strip() for c in stripped[1:-1].split('|')]
            table_rows.append(cells)
            in_table = True
            continue
        elif in_table:
            # Table ended
            if table_rows:
                formatted_table_data = []
                for row_idx, row in enumerate(table_rows):
                    row_data = []
                    for cell in row:
                        cell_clean = clean_md_inline(cell)
                        if row_idx == 0:
                            p = Paragraph(f"<b>{cell_clean}</b>", styles['TableHeader'])
                        else:
                            p = Paragraph(cell_clean, styles['TableCell'])
                        row_data.append(p)
                    formatted_table_data.append(row_data)
                
                # Create table
                col_count = len(table_rows[0])
                col_width = (letter[0] - 1.2 * inch) / col_count
                col_widths = [col_width] * col_count
                
                t = Table(formatted_table_data, colWidths=col_widths)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))
                table_rows = []
            in_table = False
            
        if not stripped:
            story.append(Spacer(1, 4))
            continue
            
        # Horizontal rules
        if stripped in ['---', '***', '___']:
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceBefore=8, spaceAfter=8))
            continue
            
        # Headers
        if stripped.startswith('# '):
            title_text = clean_md_inline(stripped[2:])
            story.append(Paragraph(title_text, styles['DocTitle']))
            story.append(Spacer(1, 10))
        elif stripped.startswith('## '):
            h1_text = clean_md_inline(stripped[3:])
            story.append(Paragraph(h1_text, styles['Heading1Custom']))
            story.append(Spacer(1, 8))
        elif stripped.startswith('### '):
            h2_text = clean_md_inline(stripped[4:])
            story.append(Paragraph(h2_text, styles['Heading2Custom']))
            story.append(Spacer(1, 6))
        elif stripped.startswith('#### '):
            h3_text = clean_md_inline(stripped[5:])
            story.append(Paragraph(h3_text, styles['Heading3Custom']))
            story.append(Spacer(1, 4))
        elif stripped.startswith('> '):
            # Blockquote
            quote_text = clean_md_inline(stripped[2:])
            story.append(Paragraph(f"<i>{quote_text}</i>", styles['BlockQuote']))
            story.append(Spacer(1, 6))
        elif stripped.startswith('* ') or stripped.startswith('- '):
            bullet_text = clean_md_inline(stripped[2:])
            story.append(Paragraph(f"• &nbsp; {bullet_text}", styles['BulletCustom']))
            story.append(Spacer(1, 3))
        elif re.match(r'^\d+\.\s', stripped):
            match = re.match(r'^(\d+\.)\s(.*)$', stripped)
            num = match.group(1)
            num_text = clean_md_inline(match.group(2))
            story.append(Paragraph(f"<b>{num}</b> &nbsp; {num_text}", styles['BulletCustom']))
            story.append(Spacer(1, 3))
        else:
            # Regular paragraph
            body_text = clean_md_inline(stripped)
            story.append(Paragraph(body_text, styles['BodyCustom']))
            story.append(Spacer(1, 4))
            
    # Handle end of table if file ends with table
    if table_rows:
        formatted_table_data = []
        for row_idx, row in enumerate(table_rows):
            row_data = []
            for cell in row:
                cell_clean = clean_md_inline(cell)
                p = Paragraph(f"<b>{cell_clean}</b>" if row_idx == 0 else cell_clean, 
                              styles['TableHeader'] if row_idx == 0 else styles['TableCell'])
                row_data.append(p)
            formatted_table_data.append(row_data)
        col_count = len(table_rows[0])
        col_width = (letter[0] - 1.2 * inch) / col_count
        t = Table(formatted_table_data, colWidths=[col_width] * col_count)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(t)
        
    return story

def create_pdf(input_md_path, output_pdf_path):
    """Converts a Markdown file into a styled PDF document."""
    with open(input_md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )

    base_styles = getSampleStyleSheet()
    styles = {}

    styles['DocTitle'] = ParagraphStyle(
        'DocTitle',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=10
    )

    styles['Heading1Custom'] = ParagraphStyle(
        'Heading1Custom',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0284C7'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    styles['Heading2Custom'] = ParagraphStyle(
        'Heading2Custom',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    styles['Heading3Custom'] = ParagraphStyle(
        'Heading3Custom',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True
    )

    styles['BodyCustom'] = ParagraphStyle(
        'BodyCustom',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B')
    )

    styles['BulletCustom'] = ParagraphStyle(
        'BulletCustom',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        leftIndent=14,
        textColor=colors.HexColor('#334155')
    )

    styles['BlockQuote'] = ParagraphStyle(
        'BlockQuote',
        parent=base_styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#3B82F6'),
        leftIndent=15,
        rightIndent=15,
        borderPadding=5,
        spaceBefore=4,
        spaceAfter=4
    )

    styles['CodeStyle'] = ParagraphStyle(
        'CodeStyle',
        parent=base_styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F1F5F9'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6
    )

    styles['TableHeader'] = ParagraphStyle(
        'TableHeader',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    styles['TableCell'] = ParagraphStyle(
        'TableCell',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    story = parse_markdown_to_story(md_text, styles)
    doc.build(story)
    print(f"Successfully generated PDF: {output_pdf_path}")

if __name__ == "__main__":
    project_root = r"c:\SIH_2026\Voice Clone Detector"
    output_dir = os.path.join(project_root, "generated_documentation_pdfs")
    os.makedirs(output_dir, exist_ok=True)

    targets = [
        ("DOCUMENTATION.md", "VoiceShield_Technical_Documentation.pdf"),
        ("README.md", "VoiceShield_Project_Overview.pdf"),
        (os.path.join("model_export", "README.md"), "VoiceShield_Transferable_Model_Guide.pdf"),
    ]

    for src_rel, dst_pdf in targets:
        src_path = os.path.join(project_root, src_rel)
        dst_path = os.path.join(output_dir, dst_pdf)
        if os.path.exists(src_path):
            print(f"Converting {src_rel} -> {dst_pdf}...")
            create_pdf(src_path, dst_path)
