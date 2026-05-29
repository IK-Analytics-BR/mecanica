"""
nfse_routes.py — NFS-e (Nota Fiscal de Serviços Eletrônica) para IKFlow Mecânica
Portado de: windsurf-project-4/app/Controllers/NfseController.php
Padrão: ABRASF 2.03 (usado pela maioria das prefeituras brasileiras)
XML gerado localmente; envio via WebService da prefeitura ou provedor (e-Nota, Betha, etc.)
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from database import get_db
from utils.auth import login_required

nfse_bp = Blueprint('nfse', __name__)

# ─────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────

def _get_config(db):
    cfg = db.fetch_one("SELECT * FROM nfse_config LIMIT 1")
    return cfg or {}


def _gerar_xml_abrasf(order: dict, cfg: dict, rps_numero: int) -> str:
    """Gera XML RPS padrão ABRASF 2.03 para envio à prefeitura."""
    agora = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    data_emissao = datetime.now().strftime('%Y-%m-%d')
    valor_servicos = float(order.get('total_geral') or 0)
    aliquota = float(cfg.get('aliquota_iss', 5.0)) / 100
    valor_iss = round(valor_servicos * aliquota, 2)
    valor_liquido = valor_servicos - float(order.get('desconto') or 0)

    discriminacao = (
        f"OS: {order.get('order_number', '')} | "
        f"Serviço mecânico: {order.get('observations', '')} | "
        f"Diagnóstico: {order.get('diagnostico', '')} | "
        f"Veículo: {order.get('equipment_name', '')} Placa: {order.get('placa', '')}"
    )[:2000]

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<EnviarLoteRpsEnvio xmlns="http://www.abrasf.org.br/nfse.xsd">
  <LoteRps versao="2.03">
    <NumeroLote>1</NumeroLote>
    <CpfCnpj><Cnpj>{cfg.get('cnpj_prestador','').replace('.','').replace('/','').replace('-','')}</Cnpj></CpfCnpj>
    <InscricaoMunicipal>{cfg.get('inscricao_municipal','')}</InscricaoMunicipal>
    <QuantidadeRps>1</QuantidadeRps>
    <ListaRps>
      <Rps>
        <InfDeclaracaoPrestacaoServico Id="rps{rps_numero}">
          <Rps>
            <IdentificacaoRps>
              <Numero>{rps_numero}</Numero>
              <Serie>{cfg.get('serie_rps','NF')}</Serie>
              <Tipo>1</Tipo>
            </IdentificacaoRps>
            <DataEmissao>{data_emissao}</DataEmissao>
            <Status>1</Status>
          </Rps>
          <Competencia>{data_emissao}</Competencia>
          <Servico>
            <Valores>
              <ValorServicos>{valor_servicos:.2f}</ValorServicos>
              <ValorDeducoes>0.00</ValorDeducoes>
              <ValorPis>0.00</ValorPis>
              <ValorCofins>0.00</ValorCofins>
              <ValorInss>0.00</ValorInss>
              <ValorIr>0.00</ValorIr>
              <ValorCsll>0.00</ValorCsll>
              <IssRetido>2</IssRetido>
              <ValorIss>{valor_iss:.2f}</ValorIss>
              <ValorIssRetido>0.00</ValorIssRetido>
              <OutrasRetencoes>0.00</OutrasRetencoes>
              <BaseCalculo>{valor_servicos:.2f}</BaseCalculo>
              <Aliquota>{aliquota:.4f}</Aliquota>
              <ValorLiquidoNfse>{valor_liquido:.2f}</ValorLiquidoNfse>
              <DescontoIncondicionado>{float(order.get('desconto') or 0):.2f}</DescontoIncondicionado>
              <DescontoCondicionado>0.00</DescontoCondicionado>
            </Valores>
            <ItemListaServico>{cfg.get('item_lista_servico','14.01')}</ItemListaServico>
            <CodigoCnae>{cfg.get('cnae','4520001')}</CodigoCnae>
            <CodigoTributacaoMunicipio>{cfg.get('codigo_tributacao','14010100')}</CodigoTributacaoMunicipio>
            <Discriminacao>{discriminacao}</Discriminacao>
            <CodigoMunicipio>{cfg.get('cod_municipio_ibge','5002704')}</CodigoMunicipio>
            <ExigibilidadeISS>{cfg.get('exigibilidade_iss','1')}</ExigibilidadeISS>
            <MunicipioIncidencia>{cfg.get('cod_municipio_ibge','5002704')}</MunicipioIncidencia>
          </Servico>
          <Prestador>
            <CpfCnpj><Cnpj>{cfg.get('cnpj_prestador','').replace('.','').replace('/','').replace('-','')}</Cnpj></CpfCnpj>
            <InscricaoMunicipal>{cfg.get('inscricao_municipal','')}</InscricaoMunicipal>
          </Prestador>
          <Tomador>
            <IdentificacaoTomador>
              <CpfCnpj>
                <Cnpj>{(order.get('customer_doc','') or '').replace('.','').replace('/','').replace('-','').replace(' ','')[:14].ljust(14,'0')}</Cnpj>
              </CpfCnpj>
            </IdentificacaoTomador>
            <RazaoSocial>{order.get('customer_name','CONSUMIDOR')[:60]}</RazaoSocial>
          </Tomador>
          <OptanteSimplesNacional>{cfg.get('simples_nacional','2')}</OptanteSimplesNacional>
          <IncentivoFiscal>2</IncentivoFiscal>
        </InfDeclaracaoPrestacaoServico>
      </Rps>
    </ListaRps>
  </LoteRps>
</EnviarLoteRpsEnvio>"""
    return xml


# ─────────────────────────────────────────────────────────────
# rotas
# ─────────────────────────────────────────────────────────────

@nfse_bp.route('/nfse')
@login_required
def nfse_lista():
    db = get_db()
    cfg = _get_config(db)
    try:
        documentos = db.fetch_all("""
            SELECT nd.*, so.order_number, c.name as customer_name
            FROM nfse_documentos nd
            LEFT JOIN service_orders so ON so.id = nd.service_order_id
            LEFT JOIN customers c ON c.id = so.customer_id
            ORDER BY nd.emitido_em DESC LIMIT 100
        """)
    except Exception:
        documentos = []
    return render_template('nfse/lista.html', documentos=documentos, cfg=cfg)


@nfse_bp.route('/nfse/configurar', methods=['GET', 'POST'])
@login_required
def nfse_config():
    db = get_db()
    cfg = _get_config(db)

    if request.method == 'POST':
        campos = [
            'cnpj_prestador', 'inscricao_municipal', 'razao_social',
            'cod_municipio_ibge', 'item_lista_servico', 'cnae',
            'codigo_tributacao', 'aliquota_iss', 'serie_rps',
            'exigibilidade_iss', 'simples_nacional', 'ambiente',
            'ws_url', 'cert_path', 'cert_password',
        ]
        dados = {c: request.form.get(c, '') for c in campos}
        try:
            if cfg:
                sets = ', '.join(f'{k}=%s' for k in dados)
                db.update(f"UPDATE nfse_config SET {sets} WHERE id=%s",
                          list(dados.values()) + [cfg['id']])
            else:
                cols = ', '.join(dados.keys())
                phs  = ', '.join(['%s'] * len(dados))
                db.insert(f"INSERT INTO nfse_config ({cols}) VALUES ({phs})",
                          list(dados.values()))
            flash('Configuração NFS-e salva!', 'success')
        except Exception as e:
            flash(f'Erro ao salvar: {e}', 'danger')
        return redirect(url_for('nfse.nfse_config'))

    return render_template('nfse/config.html', cfg=cfg)


@nfse_bp.route('/nfse/emitir/<int:order_id>', methods=['GET', 'POST'])
@login_required
def nfse_emitir(order_id):
    """Emite NFS-e para uma OS concluída."""
    db = get_db()
    cfg = _get_config(db)

    order = db.fetch_one("""
        SELECT so.*,
               c.name as customer_name, c.cnpj as customer_doc,
               e.serial_number as placa, e.name as equipment_name,
               t.name as technician_name
        FROM service_orders so
        LEFT JOIN customers c ON c.id = so.customer_id
        LEFT JOIN equipment e ON e.id = so.equipment_id
        LEFT JOIN technicians t ON t.id = so.technician_id
        WHERE so.id = %s
    """, (order_id,))

    if not order:
        flash('OS não encontrada.', 'danger')
        return redirect(url_for('service_order.service_order_list'))

    # Próximo número RPS
    try:
        ultimo = db.fetch_one("SELECT MAX(rps_numero) as ult FROM nfse_documentos")
        rps_numero = int(ultimo['ult'] or 0) + 1
    except Exception:
        rps_numero = 1

    if request.method == 'POST':
        xml_rps = _gerar_xml_abrasf(order, cfg, rps_numero)
        status_envio = 'gerado'
        numero_nfse  = None
        resposta_ws  = ''

        # Tenta enviar ao WebService da prefeitura
        ws_url = cfg.get('ws_url', '')
        if ws_url:
            try:
                headers = {'Content-Type': 'text/xml; charset=utf-8',
                           'SOAPAction': 'RecepcionarLoteRps'}
                resp = __import__('requests').post(ws_url, data=xml_rps.encode('utf-8'),
                                                   headers=headers, timeout=30)
                resposta_ws = resp.text[:2000]
                if resp.status_code == 200:
                    # Tenta extrair número da NFS-e da resposta
                    try:
                        root = ET.fromstring(resp.text)
                        ns = {'ns': 'http://www.abrasf.org.br/nfse.xsd'}
                        nfse_el = root.find('.//ns:Numero', ns)
                        if nfse_el is not None:
                            numero_nfse = nfse_el.text
                            status_envio = 'autorizada'
                    except Exception:
                        status_envio = 'enviada'
                else:
                    status_envio = 'erro_ws'
            except Exception as e:
                resposta_ws = str(e)
                status_envio = 'erro_conexao'

        # Salvar documento
        try:
            db.insert("""
                INSERT INTO nfse_documentos
                (service_order_id, rps_numero, numero_nfse, xml_rps,
                 valor, status, resposta_ws, emitido_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
            """, (order_id, rps_numero, numero_nfse,
                  xml_rps, float(order.get('total_geral') or 0),
                  status_envio, resposta_ws))
        except Exception as e:
            print(f'[NFS-e] Erro ao salvar doc: {e}')

        if status_envio == 'autorizada':
            flash(f'✅ NFS-e {numero_nfse} emitida com sucesso!', 'success')
        elif status_envio == 'gerado':
            flash('⚠️ XML gerado localmente (WebService não configurado). Envie manualmente.', 'warning')
        else:
            flash(f'❌ Erro no envio: {status_envio}. Verifique a aba de documentos.', 'danger')

        return redirect(url_for('nfse.nfse_lista'))

    xml_preview = _gerar_xml_abrasf(order, cfg, rps_numero)
    return render_template('nfse/emitir.html',
        order=order, cfg=cfg, rps_numero=rps_numero, xml_preview=xml_preview)


@nfse_bp.route('/nfse/xml/<int:doc_id>')
def nfse_download_xml(doc_id):
    db = get_db()
    doc = db.fetch_one("SELECT * FROM nfse_documentos WHERE id = %s", (doc_id,))
    if not doc:
        flash('Documento não encontrado.', 'danger')
        return redirect(url_for('nfse.nfse_lista'))
    response = make_response(doc['xml_rps'])
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Disposition'] = f'attachment; filename=nfse_rps_{doc["rps_numero"]}.xml'
    return response
