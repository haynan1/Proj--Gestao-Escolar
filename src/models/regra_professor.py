"""Regras de alocação por professor para a geração de horários.

Cada regra é tipada (ver TIPOS_REGRA), tem escopo (todas as aulas do professor ou
apenas as de uma disciplina), parâmetros em JSON, e um indicador hard/soft.
Estas regras são consumidas pelo solver CP-SAT (src/solver/horario_cpsat.py).
"""
import json
import logging

import mysql.connector

from database.connection import get_connection
from models.turno import normalizar_turno
from utils.conflitos import DIAS

_LOGGER = logging.getLogger(__name__)

# Tipos de regra suportados (espelham docs/spec-regras-e-aulas-vagas.md §4).
DIAS_PERMITIDOS = 'DIAS_PERMITIDOS'
DIAS_PROIBIDOS = 'DIAS_PROIBIDOS'
DIA_LIVRE = 'DIA_LIVRE'
DISTRIBUIR_EM_N_DIAS = 'DISTRIBUIR_EM_N_DIAS'
PERIODO_FIXO = 'PERIODO_FIXO'
PERIODO_PROIBIDO = 'PERIODO_PROIBIDO'
SLOT_FIXO = 'SLOT_FIXO'
CONTAGEM_POR_DIA = 'CONTAGEM_POR_DIA'
MAX_AULAS_DIA = 'MAX_AULAS_DIA'
AULA_GEMINADA = 'AULA_GEMINADA'

TIPOS_REGRA = {
    DIAS_PERMITIDOS,
    DIAS_PROIBIDOS,
    DIA_LIVRE,
    DISTRIBUIR_EM_N_DIAS,
    PERIODO_FIXO,
    PERIODO_PROIBIDO,
    SLOT_FIXO,
    CONTAGEM_POR_DIA,
    MAX_AULAS_DIA,
    AULA_GEMINADA,
}

TIPOS_LABEL = {
    DIAS_PERMITIDOS: 'Dias permitidos',
    DIAS_PROIBIDOS: 'Dias proibidos',
    DIA_LIVRE: 'Deixar dia(s) livre(s)',
    DISTRIBUIR_EM_N_DIAS: 'Distribuir em N dias',
    PERIODO_FIXO: 'Período fixo',
    PERIODO_PROIBIDO: 'Período proibido',
    SLOT_FIXO: 'Slot fixo (dia + período)',
    CONTAGEM_POR_DIA: 'Contagem por dia',
    MAX_AULAS_DIA: 'Máx. aulas por dia (espalhar)',
    AULA_GEMINADA: 'Aula geminada (bloco duplo)',
}

POSICOES_SLOT = {'primeiras', 'ultimas', 'periodos'}


class RegraValidationError(ValueError):
    """Erro de validação de uma regra ao cadastrar."""


def _parse_parametros(valor):
    if valor is None:
        return {}
    if isinstance(valor, (dict, list)):
        return valor
    if isinstance(valor, (bytes, bytearray)):
        valor = valor.decode('utf-8')
    try:
        return json.loads(valor)
    except (TypeError, ValueError):
        return {}


def _validar_dias(parametros):
    dias = parametros.get('dias') or []
    dias = [d for d in dias if d in DIAS]
    if not dias:
        raise RegraValidationError("Selecione ao menos um dia válido.")
    # remove duplicados preservando ordem canônica
    return {'dias': [d for d in DIAS if d in set(dias)]}


def _validar_quantidade(parametros, minimo=1, maximo=len(DIAS)):
    try:
        n = int(parametros.get('quantidade'))
    except (TypeError, ValueError):
        raise RegraValidationError("Informe uma quantidade numérica válida.")
    if n < minimo or n > maximo:
        raise RegraValidationError(f"A quantidade deve estar entre {minimo} e {maximo}.")
    return {'quantidade': n}


def _validar_periodos(parametros, chave='periodos', obrigatorio=True):
    bruto = parametros.get(chave) or []
    periodos = []
    for p in bruto:
        try:
            p = int(p)
        except (TypeError, ValueError):
            continue
        if 1 <= p <= 20:
            periodos.append(p)
    periodos = sorted(set(periodos))
    if obrigatorio and not periodos:
        raise RegraValidationError("Informe ao menos um período válido.")
    return periodos


def normalizar_parametros(tipo, parametros):
    """Valida e normaliza os parâmetros conforme o tipo. Levanta RegraValidationError."""
    parametros = parametros or {}
    if tipo in (DIAS_PERMITIDOS, DIAS_PROIBIDOS):
        return _validar_dias(parametros)

    if tipo in (DIA_LIVRE, DISTRIBUIR_EM_N_DIAS):
        # dia livre: 1..4 (não dá pra deixar todos livres); distribuir: 1..5
        maximo = len(DIAS) - 1 if tipo == DIA_LIVRE else len(DIAS)
        return _validar_quantidade(parametros, minimo=1, maximo=maximo)

    if tipo in (MAX_AULAS_DIA, AULA_GEMINADA):
        return _validar_quantidade(parametros, minimo=1, maximo=20)

    if tipo == PERIODO_FIXO:
        return {'periodos': _validar_periodos(parametros)}

    if tipo == PERIODO_PROIBIDO:
        out = {'periodos': _validar_periodos(parametros)}
        dias = [d for d in (parametros.get('dias') or []) if d in DIAS]
        if dias:
            out['dias'] = [d for d in DIAS if d in set(dias)]
        return out

    if tipo == SLOT_FIXO:
        dia = parametros.get('dia')
        if dia not in DIAS:
            raise RegraValidationError("Selecione um dia válido para o slot fixo.")
        posicao = parametros.get('posicao')
        if posicao not in POSICOES_SLOT:
            raise RegraValidationError("Posição inválida (use primeiras, ultimas ou periodos).")
        out = {'dia': dia, 'posicao': posicao}
        if posicao == 'periodos':
            out['periodos'] = _validar_periodos(parametros)
            out['quantidade'] = len(out['periodos'])
        else:
            out.update(_validar_quantidade(parametros, minimo=1, maximo=20))
        return out

    if tipo == CONTAGEM_POR_DIA:
        bruto = parametros.get('distribuicao') or {}
        distribuicao = {}
        for dia, valor in bruto.items():
            if dia not in DIAS:
                continue
            if isinstance(valor, str) and valor.strip().lower() == 'resto':
                distribuicao[dia] = 'resto'
            else:
                try:
                    distribuicao[dia] = int(valor)
                except (TypeError, ValueError):
                    continue
        if not distribuicao:
            raise RegraValidationError("Informe a distribuição por dia.")
        return {'distribuicao': distribuicao}

    raise RegraValidationError("Tipo de regra desconhecido.")


def regras_aplicaveis(regras, disciplina_id):
    """Regras que valem para uma demanda: as globais mais as da própria disciplina."""
    aplicaveis = []
    for regra in regras or []:
        escopo = regra.get('escopo_disciplina_id')
        if escopo is None or (disciplina_id is not None and int(escopo) == int(disciplina_id)):
            aplicaveis.append(regra)
    return aplicaveis


def _periodos_slot_fixo(parametros, periodos_turma):
    posicao = parametros.get('posicao')
    if posicao == 'periodos':
        return [p for p in parametros.get('periodos', []) if p in periodos_turma]
    qtd = int(parametros.get('quantidade') or 0)
    if posicao == 'primeiras':
        return list(periodos_turma[:qtd])
    if posicao == 'ultimas':
        return list(periodos_turma[-qtd:]) if qtd else []
    return []


def regra_permite_slot(regra, dia, periodo, periodos_turma):
    """A regra aceita este (dia, período)? Só olha pertinência, não cardinalidade."""
    tipo = regra.get('tipo')
    p = regra.get('parametros') or {}

    if tipo == DIAS_PERMITIDOS:
        return dia in set(p.get('dias') or [])
    if tipo == DIAS_PROIBIDOS:
        return dia not in set(p.get('dias') or [])
    if tipo == PERIODO_FIXO:
        return periodo in set(p.get('periodos') or [])
    if tipo == PERIODO_PROIBIDO:
        periodos = set(p.get('periodos') or [])
        dias_alvo = p.get('dias')
        if dias_alvo:
            return not (dia in set(dias_alvo) and periodo in periodos)
        return periodo not in periodos
    if tipo == SLOT_FIXO:
        if p.get('dia') and dia != p.get('dia'):
            return False
        return periodo in set(_periodos_slot_fixo(p, periodos_turma))
    if tipo == CONTAGEM_POR_DIA:
        return dia in set((p.get('distribuicao') or {}).keys())

    # MAX_AULAS_DIA, AULA_GEMINADA, DIA_LIVRE e DISTRIBUIR_EM_N_DIAS limitam
    # quantidade, não posição: não dá para decidi-las olhando um slot isolado.
    return True


def regra_que_bloqueia_slot(regras, dia, periodo, periodos_turma):
    """Primeira regra obrigatória que proíbe este (dia, período) — ou None.

    Devolver a regra (e não um booleano) deixa a mensagem de erro dizer o motivo.
    Regras de preferência nunca bloqueiam: elas viram penalidade no solver.
    """
    for regra in regras or []:
        if not regra.get('obrigatoria'):
            continue
        if not regra_permite_slot(regra, dia, periodo, periodos_turma):
            return regra
    return None


def slots_permitidos(regras, periodos_turma, dias_base=None):
    """Slots (dia, período) liberados pelas regras obrigatórias de pertinência.

    Fonte única usada tanto pelo solver (solver.horario_cpsat) quanto pela edição
    manual da grade (models.aula), para que gerar e arrastar sigam a mesma regra.
    """
    disponiveis = set(DIAS if dias_base is None else dias_base)
    return [
        (dia, periodo)
        for dia in DIAS if dia in disponiveis
        for periodo in periodos_turma
        if regra_que_bloqueia_slot(regras, dia, periodo, periodos_turma) is None
    ]


def carregar_regras_professor(conn, professor_id):
    """Regras ativas do professor na conexão informada (para validar dentro de uma transação)."""
    rows = conn.execute(
        """SELECT r.tipo, r.parametros, r.obrigatoria, r.peso, r.escopo_disciplina_id,
                  d.nome AS escopo_disciplina_nome
           FROM professores_regras r
           LEFT JOIN disciplinas d ON d.id = r.escopo_disciplina_id
           WHERE r.professor_id = %s AND r.ativa = 1
           ORDER BY r.id""",
        (professor_id,),
    ).fetchall()
    return [
        {
            'tipo': row['tipo'],
            'parametros': _parse_parametros(row['parametros']),
            'obrigatoria': bool(row['obrigatoria']),
            'peso': int(row['peso'] or 100),
            'escopo_disciplina_id': row['escopo_disciplina_id'],
            'escopo_disciplina_nome': row.get('escopo_disciplina_nome'),
        }
        for row in rows
    ]


def dias_efetivos(regras):
    """Dias em que o professor pode dar aula segundo as regras de dia vinculantes.

    Só entram regras obrigatórias (hard) e de escopo global — regras de preferência
    e regras restritas a uma disciplina não limitam a disponibilidade do professor
    como um todo, apenas a demanda daquela disciplina.
    """
    dias = set(DIAS)
    for regra in regras or []:
        if not regra.get('obrigatoria'):
            continue
        if regra.get('escopo_disciplina_id') is not None:
            continue
        tipo = regra.get('tipo')
        parametros = regra.get('parametros') or {}
        if tipo == DIAS_PERMITIDOS:
            dias &= set(parametros.get('dias') or [])
        elif tipo == DIAS_PROIBIDOS:
            dias -= set(parametros.get('dias') or [])
    return [d for d in DIAS if d in dias]


def dias_efetivos_de_linhas(rows):
    """dias_efetivos() a partir de linhas cruas de professores_regras."""
    return dias_efetivos([
        {
            'tipo': row['tipo'],
            'parametros': _parse_parametros(row['parametros']),
            'obrigatoria': bool(row['obrigatoria']),
            'escopo_disciplina_id': row['escopo_disciplina_id'],
        }
        for row in rows
    ])


def sincronizar_dias_disponiveis(conn, professor_id, escola_id=None, turno=None):
    """Reescreve professores.dias_disponiveis a partir das regras de dia do professor.

    As regras são a única fonte de verdade da disponibilidade semanal. A coluna
    continua existindo como cache derivado, lido pelo solver, pela validação de
    arrasto (models.aula) e pelas camadas temporárias. Retorna os dias aplicados.

    escola_id/turno restringem a escrita ao tenant informado: professor_id chega de
    parâmetro de rota em alguns fluxos, e sem esse escopo a atualização alcançaria
    professor de outra escola. Sempre passe os dois quando estiverem disponíveis.
    """
    rows = conn.execute(
        """SELECT tipo, parametros, obrigatoria, escopo_disciplina_id
           FROM professores_regras
           WHERE professor_id = %s AND ativa = 1""",
        (professor_id,),
    ).fetchall()
    dias = dias_efetivos_de_linhas(rows)

    filtros = ['id = %s']
    valores = [','.join(dias), professor_id]
    if escola_id is not None:
        filtros.append('escola_id = %s')
        valores.append(escola_id)
    if turno is not None:
        filtros.append('turno = %s')
        valores.append(turno)

    conn.execute(
        f"UPDATE professores SET dias_disponiveis = %s WHERE {' AND '.join(filtros)}",
        tuple(valores),
    )
    return dias


def _serialize_regra(row):
    item = dict(row)
    item['parametros'] = _parse_parametros(item.get('parametros'))
    item['tipo_label'] = TIPOS_LABEL.get(item.get('tipo'), item.get('tipo'))
    item['obrigatoria'] = bool(item.get('obrigatoria'))
    item['ativa'] = bool(item.get('ativa'))
    return item


def listar_regras_escola(escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT r.*, d.nome AS escopo_disciplina_nome
               FROM professores_regras r
               LEFT JOIN disciplinas d ON d.id = r.escopo_disciplina_id
               WHERE r.escola_id = %s AND r.turno = %s AND r.ativa = 1
               ORDER BY r.professor_id, r.id""",
            (escola_id, turno),
        ).fetchall()
    finally:
        conn.close()
    return [_serialize_regra(r) for r in rows]


def listar_regras_professor(professor_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT r.*, d.nome AS escopo_disciplina_nome
               FROM professores_regras r
               LEFT JOIN disciplinas d ON d.id = r.escopo_disciplina_id
               WHERE r.professor_id = %s AND r.ativa = 1
               ORDER BY r.id""",
            (professor_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_serialize_regra(r) for r in rows]


def criar_regra(escola_id, professor_id, tipo, parametros, escopo_disciplina_id=None,
                obrigatoria=True, peso=100, turno=None):
    turno = normalizar_turno(turno)
    if tipo not in TIPOS_REGRA:
        return False, "Tipo de regra inválido."

    try:
        parametros_norm = normalizar_parametros(tipo, parametros)
    except RegraValidationError as exc:
        return False, str(exc)

    try:
        peso = int(peso)
    except (TypeError, ValueError):
        peso = 100
    peso = max(1, min(peso, 1_000_000))

    conn = get_connection()
    try:
        # valida que o professor pertence à escola/turno
        prof = conn.execute(
            "SELECT id FROM professores WHERE id = %s AND escola_id = %s AND turno = %s",
            (professor_id, escola_id, turno),
        ).fetchone()
        if not prof:
            return False, "Professor não encontrado neste turno."

        disc_id = None
        if escopo_disciplina_id:
            try:
                disc_id = int(escopo_disciplina_id)
            except (TypeError, ValueError):
                disc_id = None
            if disc_id is not None:
                disc = conn.execute(
                    "SELECT id FROM disciplinas WHERE id = %s AND escola_id = %s AND turno = %s",
                    (disc_id, escola_id, turno),
                ).fetchone()
                if not disc:
                    return False, "Disciplina de escopo inválida."

        conn.execute(
            """INSERT INTO professores_regras
                   (escola_id, turno, professor_id, escopo_disciplina_id, tipo, parametros, obrigatoria, peso)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                escola_id,
                turno,
                professor_id,
                disc_id,
                tipo,
                json.dumps(parametros_norm),
                1 if obrigatoria else 0,
                peso,
            ),
        )
        sincronizar_dias_disponiveis(conn, professor_id, escola_id, turno)
        conn.commit()
        return True, "Regra adicionada com sucesso."
    except mysql.connector.Error as exc:
        conn.rollback()
        _LOGGER.error('Erro ao criar regra de professor: %s', exc)
        return False, "Erro interno ao salvar a regra. Tente novamente."
    except Exception:
        conn.rollback()
        _LOGGER.exception('Erro inesperado ao criar regra de professor.')
        raise
    finally:
        conn.close()


def deletar_regra(regra_id, escola_id, turno=None):
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        alvo = conn.execute(
            "SELECT professor_id FROM professores_regras WHERE id = %s AND escola_id = %s AND turno = %s",
            (regra_id, escola_id, turno),
        ).fetchone()
        cursor = conn.execute(
            "DELETE FROM professores_regras WHERE id = %s AND escola_id = %s AND turno = %s",
            (regra_id, escola_id, turno),
        )
        removida = cursor.rowcount > 0
        if removida and alvo:
            sincronizar_dias_disponiveis(conn, alvo['professor_id'], escola_id, turno)
        conn.commit()
        return removida
    except Exception:
        conn.rollback()
        _LOGGER.exception('Erro ao deletar regra %s.', regra_id)
        raise
    finally:
        conn.close()


def afrouxar_regras_professor(escola_id, professor_id, turno=None):
    """Marca todas as regras obrigatórias do professor como preferência (obrigatoria=0)."""
    turno = normalizar_turno(turno)
    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE professores_regras SET obrigatoria = 0
               WHERE escola_id = %s AND turno = %s AND professor_id = %s""",
            (escola_id, turno, professor_id),
        )
        # Sem regras de dia obrigatórias, o professor volta a estar livre na semana.
        sincronizar_dias_disponiveis(conn, professor_id, escola_id, turno)
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        _LOGGER.exception('Erro ao afrouxar regras do professor %s.', professor_id)
        raise
    finally:
        conn.close()


def descrever_regra(regra):
    """Texto curto e legível de uma regra, para UI/diagnóstico."""
    tipo = regra.get('tipo')
    p = regra.get('parametros') or {}
    escopo = regra.get('escopo_disciplina_nome')
    sufixo = f" (só {escopo})" if escopo else ""
    if tipo == DIAS_PERMITIDOS:
        return f"Só pode em {', '.join(p.get('dias', []))}{sufixo}"
    if tipo == DIAS_PROIBIDOS:
        return f"Não pode em {', '.join(p.get('dias', []))}{sufixo}"
    if tipo == DIA_LIVRE:
        return f"Deixar {p.get('quantidade', 1)} dia(s) livre(s){sufixo}"
    if tipo == DISTRIBUIR_EM_N_DIAS:
        return f"Distribuir em {p.get('quantidade', 2)} dias{sufixo}"
    if tipo == PERIODO_FIXO:
        return f"Apenas no(s) período(s) {', '.join(map(str, p.get('periodos', [])))}{sufixo}"
    if tipo == PERIODO_PROIBIDO:
        dias = p.get('dias')
        alvo = f" em {', '.join(dias)}" if dias else ""
        return f"Não pode no(s) período(s) {', '.join(map(str, p.get('periodos', [])))}{alvo}{sufixo}"
    if tipo == SLOT_FIXO:
        return f"{p.get('quantidade', '')} aula(s) nas {p.get('posicao')} de {p.get('dia')}{sufixo}"
    if tipo == CONTAGEM_POR_DIA:
        partes = [f"{d}: {v}" for d, v in (p.get('distribuicao') or {}).items()]
        return f"Distribuição {', '.join(partes)}{sufixo}"
    if tipo == MAX_AULAS_DIA:
        return f"No máximo {p.get('quantidade', 2)} aula(s) por dia{sufixo}"
    if tipo == AULA_GEMINADA:
        return f"{p.get('quantidade', 1)} bloco(s) de aula geminada (2 períodos seguidos){sufixo}"
    return tipo or 'regra'
