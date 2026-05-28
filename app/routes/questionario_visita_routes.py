"""Rotas para Questionário de Visita ao Cliente (genérico por segmento)."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
try:
    from services.questionario_visita_pdf import gerar_pdf_questionario
except ImportError:
    gerar_pdf_questionario = None
try:
    from services.email_service import enviar_email_com_anexo
except ImportError:
    enviar_email_com_anexo = None

import json


questionario_visita_bp = Blueprint(
    "questionario_visita",
    __name__,
    url_prefix="/questionario-visita",
)


@questionario_visita_bp.route("/salgados-congelados", methods=["GET", "POST"])
def questionario_salgados_congelados():
    """Exibe e processa o questionário de visita genérico ao cliente.

    GET: renderiza o formulário.
    POST: salva respostas, gera PDF e (opcionalmente) envia por e-mail.
    """
    if request.method == "GET":
        # Permite receber opcionalmente dados pré-preenchidos via query string
        contexto_inicial = {
            "cliente_nome": request.args.get("cliente_nome", ""),
            "cliente_email": request.args.get("cliente_email", ""),
            "cliente_cnpj": request.args.get("cliente_cnpj", ""),
            "contato_nome": request.args.get("contato_nome", ""),
            "empresa_id": request.args.get("empresa_id", ""),
            "cliente_id": request.args.get("cliente_id", ""),
            "orcamento_id": request.args.get("orcamento_id", ""),
        }
        return render_template("questionario_visita_salgados.html", contexto=contexto_inicial)

    # POST – processar respostas
    db = get_db()

    cliente_nome = request.form.get("cliente_nome", "").strip()
    cliente_email = request.form.get("cliente_email", "").strip()
    cliente_cnpj = request.form.get("cliente_cnpj", "").strip()
    cliente_telefone = request.form.get("cliente_telefone", "").strip()
    contato_nome = request.form.get("contato_nome", "").strip()
    segmento_principal = request.form.get("segmento_principal", "").strip()

    empresa_id = request.form.get("empresa_id") or None
    cliente_id = request.form.get("cliente_id") or None
    orcamento_id = request.form.get("orcamento_id") or None

    # Montar dicionário de respostas (ignorando campos de meta)
    ignore_keys = {
        "cliente_nome",
        "cliente_email",
        "cliente_cnpj",
        "cliente_telefone",
        "contato_nome",
        "segmento_principal",
        "empresa_id",
        "cliente_id",
        "orcamento_id",
        "csrf_token",
    }

    form_dict = request.form.to_dict(flat=False)
    respostas = {}
    for key, values in form_dict.items():
        if key in ignore_keys:
            continue
        if not values:
            continue
        if len(values) == 1:
            respostas[key] = values[0]
        else:
            # Ex.: checkboxes
            respostas[key] = [v for v in values if v]

    respostas_json = json.dumps(respostas, ensure_ascii=False)

    # Inserir no banco
    insert_sql = """
        INSERT INTO customer_visit_questionnaires (
            empresa_id,
            cliente_id,
            orcamento_id,
            cliente_nome,
            cliente_email,
            cliente_cnpj,
            cliente_telefone,
            contato_nome,
            segmento_principal,
            respostas_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    questionario_id = db.insert(
        insert_sql,
        (
            empresa_id,
            cliente_id,
            orcamento_id,
            cliente_nome,
            cliente_email,
            cliente_cnpj,
            cliente_telefone,
            contato_nome,
            segmento_principal,
            respostas_json,
        ),
    )

    contexto = {
        "cliente_nome": cliente_nome,
        "cliente_email": cliente_email,
        "cliente_cnpj": cliente_cnpj,
        "contato_nome": contato_nome,
        "segmento_principal": segmento_principal,
    }

    pdf_buffer = gerar_pdf_questionario(contexto, respostas)

    # Enviar e-mail, se fornecido
    if cliente_email:
        try:
            assunto = f"Questionário de Visita – {cliente_nome or 'Cliente'}"
            corpo_html = (
                "<p>Segue em anexo o questionário de visita respondido em nossa reunião."  # noqa: E501
                "<br>Obrigado pelo seu tempo!</p>"
            )

            enviar_email_com_anexo(
                destinatario=cliente_email,
                assunto=assunto,
                corpo_html=corpo_html,
                anexo=pdf_buffer.getvalue(),
                nome_anexo=f"questionario_visita_{questionario_id}.pdf",
                empresa_id=empresa_id,
            )

            # Atualizar marcação de envio
            db.update(
                "UPDATE customer_visit_questionnaires SET enviado_email = 1, enviado_email_em = NOW() WHERE id = %s",
                (questionario_id,),
            )
        except Exception as e:  # pragma: no cover – apenas log
            print(f"[QUESTIONARIO] Erro ao enviar email: {e}")

    # Retornar o PDF para visualização imediata no navegador
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers[
        "Content-Disposition"
    ] = f"inline; filename=questionario_visita_{questionario_id}.pdf"

    return response


@questionario_visita_bp.route("/", methods=["GET", "POST"])
@questionario_visita_bp.route("/geral", methods=["GET", "POST"])
def questionario_visita_geral():
    """Alias genérico para o questionário de visita."""
    return questionario_salgados_congelados()
