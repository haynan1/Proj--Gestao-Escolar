import os
import tempfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']
PERIODOS = [1, 2, 3, 4, 5]


def hex_to_color(hex_str):
    """Converte #rrggbb para reportlab Color."""
    try:
        h = hex_str.lstrip('#')
        r = int(h[0:2], 16) / 255
        g = int(h[2:4], 16) / 255
        b = int(h[4:6], 16) / 255
        return colors.Color(r, g, b)
    except Exception:
        return colors.HexColor('#22c55e')


def hex_to_light(hex_str, alpha=0.15):
    """Retorna versão clara da cor para fundo."""
    try:
        h = hex_str.lstrip('#')
        r = int(h[0:2], 16) / 255
        g = int(h[2:4], 16) / 255
        b = int(h[4:6], 16) / 255
        # Mistura com branco
        r2 = r + (1 - r) * (1 - alpha)
        g2 = g + (1 - g) * (1 - alpha)
        b2 = b + (1 - b) * (1 - alpha)
        return colors.Color(r2, g2, b2)
    except Exception:
        return colors.white


def exportar_pdf(escola, aulas, turmas, disciplinas):
    """Gera PDF com a grade de horários por turma."""
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        fontSize=16, textColor=colors.HexColor('#22c55e'),
        spaceAfter=4, fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#94a3b8'),
        spaceAfter=12
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=TA_CENTER
    )

    # Cores de fundo
    BG_DARK  = colors.HexColor('#0f172a')
    BG_CARD  = colors.HexColor('#1e293b')
    BG_ROW   = colors.HexColor('#273549')
    TEXT_COL = colors.HexColor('#f1f5f9')
    TEXT_MUT = colors.HexColor('#94a3b8')
    GREEN    = colors.HexColor('#22c55e')

    # Índice de aulas
    idx = {}
    for a in aulas:
        tid = a['turma_id']
        if tid not in idx:
            idx[tid] = {}
        dia = a['dia']
        if dia not in idx[tid]:
            idx[tid][dia] = {}
        idx[tid][dia][a['periodo']] = a

    story = []

    for i, turma in enumerate(turmas):
        if i > 0:
            story.append(PageBreak())

        story.append(Paragraph(f"Horário Escolar — {turma['nome']}", title_style))
        story.append(Paragraph(escola['nome'], subtitle_style))

        # Monta tabela
        header_row = ['Dia'] + [f'{p}º' for p in PERIODOS]
        table_data = [header_row]

        for dia in DIAS:
            row = [dia]
            for periodo in PERIODOS:
                aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
                if aula:
                    txt = f"<b>{aula['disciplina_nome']}</b><br/><font size='7' color='#94a3b8'>{aula['professor_nome']}</font>"
                    row.append(Paragraph(txt, cell_style))
                else:
                    row.append('')
            table_data.append(row)

        col_widths = [3 * cm] + [4.5 * cm] * 5
        t = Table(table_data, colWidths=col_widths, rowHeights=[1.2 * cm] + [2 * cm] * 5)

        # Estilos da tabela
        ts = [
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), BG_CARD),
            ('TEXTCOLOR',  (0, 0), (-1, 0), TEXT_COL),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),

            # Coluna de dias
            ('BACKGROUND', (0, 1), (0, -1), BG_ROW),
            ('TEXTCOLOR',  (0, 1), (0, -1), TEXT_MUT),
            ('FONTNAME',   (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 1), (0, -1), 9),
            ('ALIGN',      (0, 1), (0, -1), 'CENTER'),

            # Células de aula
            ('BACKGROUND', (1, 1), (-1, -1), BG_CARD),
            ('ALIGN',      (1, 1), (-1, -1), 'CENTER'),

            # Grade
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#334155')),
            ('ROWBACKGROUNDS', (1, 1), (-1, -1), [BG_CARD, BG_ROW]),
        ]

        # Cores individuais por aula
        for row_idx, dia in enumerate(DIAS, 1):
            for col_idx, periodo in enumerate(PERIODOS, 1):
                aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
                if aula:
                    try:
                        bg = hex_to_light(aula['disciplina_cor'], 0.85)
                        ts.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg))
                    except Exception:
                        pass

        t.setStyle(TableStyle(ts))
        story.append(t)

        # Legenda
        story.append(Spacer(1, 0.5 * cm))

        seen = set()
        leg_items = []
        for a in aulas:
            if a['turma_id'] == turma['id'] and a['disciplina_id'] not in seen:
                seen.add(a['disciplina_id'])
                cor = hex_to_color(a['disciplina_cor'])
                leg_items.append(
                    f"<font color='{a['disciplina_cor']}'>■</font> "
                    f"<b>{a['disciplina_nome']}</b> — {a['professor_nome']}"
                )

        if leg_items:
            legend_style = ParagraphStyle(
                'Legend', parent=styles['Normal'],
                fontSize=8, textColor=TEXT_COL, leading=14
            )
            story.append(Paragraph('<br/>'.join(leg_items), legend_style))

    doc.build(story)
    return tmp.name
