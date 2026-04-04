import os
import tempfile
import openpyxl
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side,
                              GradientFill)
from openpyxl.utils import get_column_letter

DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta']
PERIODOS = [1, 2, 3, 4, 5]


def hex_to_argb(hex_color):
    """Converte #rrggbb para AARRGGBB (openpyxl)."""
    h = hex_color.lstrip('#')
    if len(h) == 6:
        return 'FF' + h.upper()
    return 'FF22C55E'


def exportar_excel(escola, aulas, turmas):
    """Gera arquivo Excel com a grade de horários por turma."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove aba padrão

    # Estilos base
    thin = Side(style='thin', color='334155')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    header_font = Font(name='Calibri', bold=True, color='F1F5F9', size=11)
    header_fill = PatternFill('solid', fgColor='1E293B')
    dia_font = Font(name='Calibri', bold=True, color='94A3B8', size=10)
    dia_fill = PatternFill('solid', fgColor='273549')
    title_font = Font(name='Calibri', bold=True, color='22C55E', size=14)

    # Monta índice de aulas: turma_id -> dia -> periodo -> aula
    idx = {}
    for a in aulas:
        tid = a['turma_id']
        if tid not in idx:
            idx[tid] = {}
        dia = a['dia']
        if dia not in idx[tid]:
            idx[tid][dia] = {}
        idx[tid][dia][a['periodo']] = a

    for turma in turmas:
        ws = wb.create_sheet(title=turma['nome'][:31])
        ws.sheet_view.showGridLines = False

        # Título
        ws.merge_cells('A1:G1')
        ws['A1'] = f"Horário — {turma['nome']} | {escola['nome']}"
        ws['A1'].font = title_font
        ws['A1'].fill = PatternFill('solid', fgColor='0F172A')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 36

        # Cabeçalho: Dia + Períodos
        ws.row_dimensions[2].height = 28
        headers = ['Dia / Período'] + [f'{p}º Período' for p in PERIODOS]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border

        # Larguras
        ws.column_dimensions['A'].width = 14
        for col in range(2, 7):
            ws.column_dimensions[get_column_letter(col)].width = 22

        # Linhas de dias
        for row_idx, dia in enumerate(DIAS, 3):
            ws.row_dimensions[row_idx].height = 52

            # Célula do dia
            cell_dia = ws.cell(row=row_idx, column=1, value=dia)
            cell_dia.font = dia_font
            cell_dia.fill = dia_fill
            cell_dia.alignment = Alignment(horizontal='center', vertical='center')
            cell_dia.border = border

            for col_idx, periodo in enumerate(PERIODOS, 2):
                aula = idx.get(turma['id'], {}).get(dia, {}).get(periodo)
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                if aula:
                    cell.value = f"{aula['disciplina_nome']}\n{aula['professor_nome']}"
                    # Fundo suave: mistura a cor com branco
                    try:
                        bg = aula['disciplina_cor'].lstrip('#')
                        r = min(255, int(bg[0:2], 16) + 180)
                        g = min(255, int(bg[2:4], 16) + 180)
                        b = min(255, int(bg[4:6], 16) + 180)
                        fgColor = f'FF{r:02X}{g:02X}{b:02X}'
                        cell.fill = PatternFill('solid', fgColor=fgColor)
                        cell.font = Font(name='Calibri', bold=True, size=9,
                                         color=hex_to_argb(aula['disciplina_cor']))
                    except Exception:
                        cell.fill = PatternFill('solid', fgColor='FF273549')
                        cell.font = Font(name='Calibri', bold=True, size=9, color='FFF1F5F9')
                else:
                    cell.fill = PatternFill('solid', fgColor='FF1E293B')

        # Legenda
        legend_row = len(DIAS) + 4
        ws.cell(row=legend_row, column=1, value='Legenda:').font = Font(
            bold=True, color='F1F5F9', size=10)

        seen = set()
        leg_col = 1
        for a in aulas:
            if a['turma_id'] == turma['id'] and a['disciplina_id'] not in seen:
                seen.add(a['disciplina_id'])
                cell = ws.cell(row=legend_row + 1, column=leg_col,
                               value=f"■ {a['disciplina_nome']} — {a['professor_nome']}")
                try:
                    cell.font = Font(color=hex_to_argb(a['disciplina_cor']), size=9, bold=True)
                except Exception:
                    pass
                leg_col += 1
                if leg_col > 6:
                    leg_col = 1
                    legend_row += 1

    # Salva em arquivo temporário
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    wb.save(tmp.name)
    tmp.close()
    return tmp.name
