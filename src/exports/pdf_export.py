import tempfile
from datetime import datetime
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']

PAGE_BG = colors.HexColor('#f8fafc')
INK = colors.HexColor('#0f172a')
MUTED = colors.HexColor('#64748b')
LINE = colors.HexColor('#cbd5e1')
NAVY = colors.HexColor('#111827')
NAVY_2 = colors.HexColor('#1e293b')
GREEN = colors.HexColor('#22c55e')
EMPTY_BG = colors.HexColor('#f1f5f9')


def hex_to_color(hex_str):
    """Converte #rrggbb para reportlab Color."""
    try:
        h = hex_str.lstrip('#')
        return colors.Color(
            int(h[0:2], 16) / 255,
            int(h[2:4], 16) / 255,
            int(h[4:6], 16) / 255,
        )
    except Exception:
        return GREEN


def hex_to_light(hex_str, tint=0.86):
    """Mistura a cor da disciplina com branco para um fundo suave de impressão."""
    try:
        base = hex_to_color(hex_str)
        return colors.Color(
            base.red + (1 - base.red) * tint,
            base.green + (1 - base.green) * tint,
            base.blue + (1 - base.blue) * tint,
        )
    except Exception:
        return colors.white


def _hex_color(hex_str, fallback='#22c55e'):
    try:
        h = hex_str.strip()
        if len(h) == 7 and h.startswith('#'):
            int(h[1:], 16)
            return h
    except Exception:
        pass
    return fallback


def _build_index(aulas):
    idx = {}
    for aula in aulas:
        idx.setdefault(aula['turma_id'], {}).setdefault(aula['dia'], {})[aula['periodo']] = aula
    return idx


def _periodos_turma(turma):
    aulas_por_dia = int(turma.get('aulas_por_dia') or 5)
    return list(range(1, aulas_por_dia + 1))


def _normalize_color_mode(color_mode):
    return color_mode if color_mode in {'disciplina', 'professor', 'none'} else 'disciplina'


def _aula_color(aula, color_mode):
    if color_mode == 'professor':
        return _hex_color(aula.get('professor_cor', '#22c55e'))
    if color_mode == 'disciplina':
        return _hex_color(aula.get('disciplina_cor', '#22c55e'))
    return None


def _schedule_cell(aula, styles, color_mode):
    if not aula:
        return Paragraph('—', styles['empty'])

    cor = _aula_color(aula, color_mode)
    disciplina_cor = cor or '#0f172a'
    texto = (
        f"<font color='{disciplina_cor}'><b>{escape(aula['disciplina_nome'])}</b></font>"
        f"<br/><font color='#475569'>{escape(aula['professor_nome'])}</font>"
    )
    return Paragraph(texto, styles['cell'])


def _draw_page(canvas, doc):
    width, height = landscape(A4)
    canvas.saveState()
    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 0.35 * cm, width, 0.35 * cm, fill=1, stroke=0)

    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 7)
    canvas.drawRightString(width - doc.rightMargin, 0.55 * cm, f'Página {doc.page}')
    canvas.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        'eyebrow': ParagraphStyle(
            'Eyebrow',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=GREEN,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        'title': ParagraphStyle(
            'ScheduleTitle',
            parent=base['Title'],
            fontName='Helvetica-Bold',
            fontSize=21,
            leading=24,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'ScheduleSubtitle',
            parent=base['Normal'],
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        'meta': ParagraphStyle(
            'ScheduleMeta',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        'cell': ParagraphStyle(
            'ScheduleCell',
            parent=base['Normal'],
            fontSize=8.5,
            leading=10,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'empty': ParagraphStyle(
            'ScheduleEmpty',
            parent=base['Normal'],
            fontSize=12,
            leading=12,
            textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER,
        ),
        'legend': ParagraphStyle(
            'ScheduleLegend',
            parent=base['Normal'],
            fontSize=8,
            leading=11,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        'matrix_header': ParagraphStyle(
            'ScheduleMatrixHeader',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=6.8,
            leading=7.5,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def _header(escola, turma, styles):
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    title_block = [
        Paragraph('GRADE DE HORÁRIOS', styles['eyebrow']),
        Paragraph(escape(turma['nome']), styles['title']),
        Paragraph(f"{escape(escola['nome'])}<br/>Atualizado em {generated_at}", styles['subtitle']),
    ]
    meta = Table(
        [[Paragraph('Flowter', styles['meta'])], [Paragraph('Gestão escolar', styles['meta'])]],
        colWidths=[4.1 * cm],
        rowHeights=[0.65 * cm, 0.55 * cm],
    )
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), GREEN),
        ('BACKGROUND', (0, 1), (0, 1), NAVY_2),
        ('BOX', (0, 0), (-1, -1), 0.25, NAVY_2),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    header = Table([[title_block, meta]], colWidths=[21.3 * cm, 4.1 * cm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return header


def _schedule_table(turma, idx, styles, color_mode='disciplina'):
    color_mode = _normalize_color_mode(color_mode)
    periodos = _periodos_turma(turma)
    header_row = ['Dia / Período'] + [f'{periodo}º Período' for periodo in periodos]
    table_data = [header_row]

    for dia in DIAS:
        row = [dia]
        for periodo in periodos:
            aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
            if aula:
                cor = _aula_color(aula, color_mode)
                disciplina_cor = cor or '#0f172a'
                texto = (
                    f"<font color='{disciplina_cor}'><b>{escape(aula['disciplina_nome'])}</b></font>"
                    f"<br/><font color='#475569'>{escape(aula['professor_nome'])}</font>"
                )
                row.append(Paragraph(texto, styles['cell']))
            else:
                row.append(Paragraph('—', styles['empty']))
        table_data.append(row)

    table = Table(
        table_data,
        colWidths=[3.2 * cm] + [(22.2 / len(periodos)) * cm] * len(periodos),
        rowHeights=[1.05 * cm] + [2.15 * cm] * len(DIAS),
        repeatRows=1,
    )

    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 1), (0, -1), INK),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (0, -1), 8.5),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('BACKGROUND', (1, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.45, LINE),
        ('BOX', (0, 0), (-1, -1), 0.8, NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]

    for row_idx, dia in enumerate(DIAS, 1):
        for col_idx, periodo in enumerate(periodos, 1):
            aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
            if aula:
                cor = _aula_color(aula, color_mode)
                table_style.append((
                    'BACKGROUND',
                    (col_idx, row_idx),
                    (col_idx, row_idx),
                    hex_to_light(cor) if cor else colors.white,
                ))
            else:
                table_style.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), EMPTY_BG))

    table.setStyle(TableStyle(table_style))
    return table


def _schedule_table_transposed(turma, idx, styles, color_mode='disciplina'):
    color_mode = _normalize_color_mode(color_mode)
    periodos = _periodos_turma(turma)
    header_row = ['Período / Dia'] + DIAS
    table_data = [header_row]

    for periodo in periodos:
        row = [f'{periodo}º Período']
        for dia in DIAS:
            aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
            row.append(_schedule_cell(aula, styles, color_mode))
        table_data.append(row)

    table = Table(
        table_data,
        colWidths=[3.2 * cm] + [(22.2 / len(DIAS)) * cm] * len(DIAS),
        rowHeights=[1.05 * cm] + [2.15 * cm] * len(periodos),
        repeatRows=1,
    )

    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 1), (0, -1), INK),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (0, -1), 8.5),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('BACKGROUND', (1, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.45, LINE),
        ('BOX', (0, 0), (-1, -1), 0.8, NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]

    for row_idx, periodo in enumerate(periodos, 1):
        for col_idx, dia in enumerate(DIAS, 1):
            aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
            if aula:
                cor = _aula_color(aula, color_mode)
                table_style.append((
                    'BACKGROUND',
                    (col_idx, row_idx),
                    (col_idx, row_idx),
                    hex_to_light(cor) if cor else colors.white,
                ))
            else:
                table_style.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), EMPTY_BG))

    table.setStyle(TableStyle(table_style))
    return table


def _legend(turma, aulas, styles):
    seen = set()
    items = []
    for aula in aulas:
        if aula['turma_id'] != turma['id'] or aula['disciplina_id'] in seen:
            continue
        seen.add(aula['disciplina_id'])
        cor = _hex_color(aula.get('disciplina_cor', '#22c55e'))
        items.append(Paragraph(
            f"<font color='{cor}'>■</font> <b>{escape(aula['disciplina_nome'])}</b><br/>"
            f"<font color='#64748b'>{escape(aula['professor_nome'])}</font>",
            styles['legend'],
        ))

    if not items:
        return Paragraph('Nenhuma aula gerada para esta turma.', styles['subtitle'])

    rows = []
    for i in range(0, len(items), 3):
        row = items[i:i + 3]
        while len(row) < 3:
            row.append('')
        rows.append(row)

    table = Table(rows, colWidths=[8.35 * cm, 8.35 * cm, 8.35 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.45, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return table


def _matrix_cell_style(name, font_size, leading, color=INK, bold=False):
    return ParagraphStyle(
        name,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=font_size,
        leading=leading,
        textColor=color,
        alignment=TA_LEFT,
    )


def _matrix_text(aula, color_mode, font_size, leading):
    if not aula:
        return ''

    cor = _aula_color(aula, color_mode)
    disciplina_cor = cor or '#0f172a'
    style = _matrix_cell_style('MatrixCell', font_size, leading)
    return Paragraph(
        f"<font color='{disciplina_cor}'><b>{escape(aula['disciplina_nome'])}</b></font>"
        f"<br/><font color='#64748b'>{escape(aula['professor_nome'])}</font>",
        style,
    )


def _matrix_table(turmas, idx, styles, color_mode='none'):
    color_mode = _normalize_color_mode(color_mode)
    max_periodos = max([len(_periodos_turma(turma)) for turma in turmas] or [5])
    data_rows = len(DIAS) * max_periodos
    available_width = landscape(A4)[0] - (1.0 * cm)
    available_height = landscape(A4)[1] - (2.2 * cm)

    day_col_width = 1.65 * cm
    period_col_width = 0.58 * cm
    turma_col_width = (available_width - day_col_width - period_col_width) / max(len(turmas), 1)
    header_height = 0.52 * cm
    row_height = max(0.28 * cm, (available_height - header_height) / max(data_rows, 1))
    font_size = max(4.15, min(6.25, (turma_col_width / cm) * 1.1, (row_height / cm) * 7.7))
    leading = font_size + 1.0

    table_data = [['Dia', 'P'] + [Paragraph(escape(turma['nome']), styles['matrix_header']) for turma in turmas]]
    for dia in DIAS:
        for periodo in range(1, max_periodos + 1):
            row = [dia if periodo == 1 else '', f'{periodo}º']
            for turma in turmas:
                aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
                row.append(_matrix_text(aula, color_mode, font_size, leading))
            table_data.append(row)

    table = Table(
        table_data,
        colWidths=[day_col_width, period_col_width] + [turma_col_width] * len(turmas),
        rowHeights=[header_height] + [row_height] * data_rows,
        repeatRows=1,
    )

    table_style = [
        ('GRID', (0, 0), (-1, -1), 0.28, colors.HexColor('#d7dde6')),
        ('BOX', (0, 0), (-1, -1), 0.55, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 6.8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2.6),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (1, -1), 6.5),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('TEXTCOLOR', (1, 1), (1, -1), MUTED),
        ('BACKGROUND', (1, 1), (1, -1), colors.HexColor('#f8fafc')),
    ]

    current_row = 1
    for day_idx, dia in enumerate(DIAS):
        start_row = current_row
        end_row = current_row + max_periodos - 1
        day_bg = colors.HexColor('#eef2f7') if day_idx % 2 == 0 else colors.HexColor('#f8fafc')
        table_style.extend([
            ('SPAN', (0, start_row), (0, end_row)),
            ('BACKGROUND', (0, start_row), (0, end_row), day_bg),
            ('TEXTCOLOR', (0, start_row), (0, end_row), INK),
            ('LINEAFTER', (1, start_row), (1, end_row), 0.5, colors.HexColor('#cbd5e1')),
        ])
        if dia != DIAS[0]:
            table_style.append(('LINEABOVE', (0, start_row), (-1, start_row), 0.85, colors.HexColor('#94a3b8')))

        for periodo in range(1, max_periodos + 1):
            row_idx = current_row + periodo - 1
            if periodo % 2 == 0:
                table_style.append(('BACKGROUND', (2, row_idx), (-1, row_idx), colors.HexColor('#fbfdff')))
            for col_idx, turma in enumerate(turmas, 2):
                aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
                if aula:
                    cor = _aula_color(aula, color_mode)
                    table_style.append((
                        'BACKGROUND',
                        (col_idx, row_idx),
                        (col_idx, row_idx),
                        hex_to_light(cor, 0.9) if cor else colors.white,
                    ))
        current_row += max_periodos

    table.setStyle(TableStyle(table_style))
    return table


def exportar_pdf_matriz(escola, aulas, turmas, color_mode='none'):
    """Gera PDF com todas as turmas em uma unica pagina."""
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=landscape(A4),
        rightMargin=0.5 * cm,
        leftMargin=0.5 * cm,
        topMargin=0.45 * cm,
        bottomMargin=0.45 * cm,
    )

    styles = _styles()
    idx = _build_index(aulas)
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    title_style = ParagraphStyle(
        'MatrixTitle',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=INK,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        'MatrixSubtitle',
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=MUTED,
        alignment=TA_LEFT,
    )

    story = [
        Paragraph(f"Grade geral de horarios - {escape(escola['nome'])}", title_style),
        Paragraph(f"Todas as turmas em uma pagina | Atualizado em {generated_at}", subtitle_style),
        Spacer(1, 0.12 * cm),
        _matrix_table(turmas, idx, styles, color_mode=color_mode),
    ]

    doc.build(story)
    return tmp.name


def exportar_pdf(escola, aulas, turmas, disciplinas, color_mode='disciplina', transpor_grade=False):
    """Gera PDF com a grade de horários por turma."""
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=landscape(A4),
        rightMargin=1.0 * cm,
        leftMargin=1.0 * cm,
        topMargin=0.85 * cm,
        bottomMargin=0.9 * cm,
    )

    styles = _styles()
    idx = _build_index(aulas)
    story = []

    for index, turma in enumerate(turmas):
        if index > 0:
            story.append(PageBreak())

        story.append(KeepTogether([
            _header(escola, turma, styles),
            Spacer(1, 0.4 * cm),
            (
                _schedule_table_transposed(turma, idx, styles, color_mode=color_mode)
                if transpor_grade
                else _schedule_table(turma, idx, styles, color_mode=color_mode)
            ),
        ]))

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return tmp.name


def exportar_relatorio_mensal_pdf(
    escola,
    turno_label,
    mes_label,
    registros,
    resumo,
    camadas_temporarias,
    resumo_camadas,
    tipos_ocorrencia,
):
    """Gera PDF mensal com registros, tratativas e camadas temporarias."""
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )
    base = getSampleStyleSheet()
    styles = {
        'eyebrow': ParagraphStyle(
            'ReportEyebrow',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=GREEN,
            spaceAfter=3,
        ),
        'title': ParagraphStyle(
            'ReportTitle',
            parent=base['Title'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=3,
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle',
            parent=base['Normal'],
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=10,
        ),
        'section': ParagraphStyle(
            'ReportSection',
            parent=base['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=6,
        ),
        'cell': ParagraphStyle(
            'ReportCell',
            parent=base['Normal'],
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
        'muted': ParagraphStyle(
            'ReportMuted',
            parent=base['Normal'],
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
    }

    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    story = [
        Paragraph('RELATORIO MENSAL', styles['eyebrow']),
        Paragraph(f"{escape(escola['nome'])}", styles['title']),
        Paragraph(f"{escape(mes_label)} | {escape(turno_label)} | Gerado em {generated_at}", styles['subtitle']),
    ]

    summary_data = [
        ['Registros', 'Faltas', 'Ocorrencias', 'Professores', 'Camadas', 'Aulas impactadas'],
        [
            str(resumo.get('total', 0)),
            str(resumo.get('faltas', 0)),
            str(resumo.get('ocorrencias', 0)),
            str(resumo.get('professores_envolvidos', 0)),
            str(resumo_camadas.get('total', 0)),
            str(resumo_camadas.get('aulas', 0)),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[3.0 * cm, 2.2 * cm, 2.8 * cm, 2.8 * cm, 2.4 * cm, 3.4 * cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.35, LINE),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.extend([summary_table, Spacer(1, 0.25 * cm), Paragraph('Registros e tratativas', styles['section'])])

    if registros:
        rows = [['Data', 'Tipo', 'Professor', 'Descricao', 'Registro']]
        for registro in registros:
            rows.append([
                Paragraph(escape(str(registro.get('data_formatada') or registro.get('data_ocorrencia') or '-')), styles['cell']),
                Paragraph(escape(tipos_ocorrencia.get(registro.get('tipo'), registro.get('tipo') or '-')), styles['cell']),
                Paragraph(escape(registro.get('professor_nome') or 'Professor removido'), styles['cell']),
                Paragraph(escape(registro.get('descricao') or '-'), styles['cell']),
                Paragraph(escape(registro.get('criado_por_nome') or 'Sistema'), styles['muted']),
            ])
        table = Table(rows, colWidths=[2.0 * cm, 2.2 * cm, 3.5 * cm, 7.0 * cm, 2.8 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_2),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.3, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph('Nenhum registro de professor neste mes.', styles['muted']))

    story.append(Paragraph('Camadas temporarias de horario', styles['section']))
    if camadas_temporarias:
        rows = [['Periodo', 'Dia', 'Titulo', 'Tratativa', 'Impacto']]
        for camada in camadas_temporarias:
            periodo = camada.get('data_inicio_formatada') or str(camada.get('data_inicio') or '-')
            if camada.get('data_fim') != camada.get('data_inicio'):
                periodo = f"{periodo} ate {camada.get('data_fim_formatada') or camada.get('data_fim')}"
            rows.append([
                Paragraph(escape(str(periodo)), styles['cell']),
                Paragraph(escape(camada.get('dia') or '-'), styles['cell']),
                Paragraph(escape(camada.get('titulo') or 'Alternativo'), styles['cell']),
                Paragraph(escape(camada.get('observacao') or '-'), styles['cell']),
                Paragraph(escape(f"{camada.get('total_turmas', 0)} turma(s), {camada.get('total_aulas', 0)} aula(s)"), styles['cell']),
            ])
        table = Table(rows, colWidths=[3.0 * cm, 2.2 * cm, 4.0 * cm, 5.3 * cm, 3.0 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_2),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.3, LINE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph('Nenhuma camada temporaria com validade neste mes.', styles['muted']))

    doc.build(story)
    return tmp.name
