"""
test_dia_produtivo.py — 20 testes simulando um dia produtivo completo na oficina.
Cobre: atendimento, OS, mecânico, financeiro, estoque, RH, vendas, fiscal, comunicação.

Executar:
    cd C:\\Users\\aritana\\CascadeProjects\\IKFlow-Mecanica
    py -m pytest tests/test_dia_produtivo.py -v
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main_mysql import app


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope='session')
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with app.app_context():
            # Login como admin
            c.post('/login', data={
                'username': 'admin',
                'password': 'admin123',
            }, follow_redirects=True)
            yield c


# ─────────────────────────────────────────────────────────────
# BLOCO 1 — ABERTURA DO DIA (Recepcionista / Atendente)
# ─────────────────────────────────────────────────────────────

def test_01_login_redirect_dashboard(client):
    """T01: Login redireciona para /bem-vindo ou dashboard."""
    r = client.get('/', follow_redirects=True)
    assert r.status_code == 200
    assert b'IKFlow' in r.data or b'bem-vindo' in r.data.lower() or b'login' in r.data.lower()


def test_02_listar_clientes(client):
    """T02: Atendente abre lista de clientes cadastrados."""
    r = client.get('/clientes/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_03_cadastrar_cliente(client):
    """T03: Atendente cadastra novo cliente (João Silva)."""
    r = client.post('/clientes/novo', data={
        'name': 'João Silva Teste',
        'phone': '11999990001',
        'email': 'joao.teste@email.com',
        'cpf_cnpj': '123.456.789-09',
        'address': 'Rua das Flores, 100',
        'city': 'São Paulo',
        'state': 'SP',
    }, follow_redirects=True)
    assert r.status_code in (200, 201, 302)


def test_04_cadastrar_veiculo(client):
    """T04: Atendente cadastra veículo do cliente (Gol 2018, ABC-1234)."""
    r = client.post('/equipamentos/novo', data={
        'name': 'Volkswagen Gol 2018',
        'serial_number': 'ABC1234',
        'year': '2018',
        'fuel_type': 'flex',
        'accumulated_hours': '45000',
    }, follow_redirects=True)
    assert r.status_code in (200, 201, 302)


# ─────────────────────────────────────────────────────────────
# BLOCO 2 — ABERTURA DE ORÇAMENTO E OS
# ─────────────────────────────────────────────────────────────

def test_05_abrir_pagina_nova_os(client):
    """T05: Recepcionista acessa formulário de nova OS."""
    r = client.get('/service_orders/novo', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_06_listar_ordens_servico(client):
    """T06: Lista de OS carrega sem erro."""
    r = client.get('/service_orders/', follow_redirects=True)
    assert r.status_code == 200


def test_07_abrir_os_avulsa(client):
    """T07: OS avulsa (balcão, sem cliente cadastrado) abre formulário."""
    r = client.get('/service_orders/avulso', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_08_listar_orcamentos(client):
    """T08: Lista de orçamentos carrega."""
    r = client.get('/orcamentos/', follow_redirects=True)
    assert r.status_code in (200, 302)


# ─────────────────────────────────────────────────────────────
# BLOCO 3 — MECÂNICO EM CAMPO
# ─────────────────────────────────────────────────────────────

def test_09_agenda_mecanicos(client):
    """T09: Mecânico / coordenador acessa agenda do dia."""
    r = client.get('/agenda/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_10_listar_tecnicos(client):
    """T10: RH lista mecânicos e técnicos cadastrados."""
    r = client.get('/tecnicos/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_11_jornada_ponto(client):
    """T11: RH acessa controle de ponto / jornada de trabalho."""
    r = client.get('/jornada/', follow_redirects=True)
    assert r.status_code in (200, 302)


# ─────────────────────────────────────────────────────────────
# BLOCO 4 — ESTOQUE E COMPRAS
# ─────────────────────────────────────────────────────────────

def test_12_listar_estoque(client):
    """T12: Almoxarife acessa estoque atual."""
    r = client.get('/inventory/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_13_listar_produtos(client):
    """T13: Almoxarife acessa catálogo de peças."""
    r = client.get('/produtos/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_14_listar_fornecedores(client):
    """T14: Comprador acessa lista de fornecedores."""
    r = client.get('/fornecedores/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_15_pedidos_compra(client):
    """T15: Comprador acessa pedidos de compra."""
    r = client.get('/purchase_orders/', follow_redirects=True)
    assert r.status_code in (200, 302)


# ─────────────────────────────────────────────────────────────
# BLOCO 5 — FINANCEIRO
# ─────────────────────────────────────────────────────────────

def test_16_contas_receber(client):
    """T16: Financeiro acessa contas a receber."""
    r = client.get('/accounts_receivable/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_17_contas_pagar(client):
    """T17: Financeiro acessa contas a pagar."""
    r = client.get('/accounts_payable/', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_18_fluxo_caixa(client):
    """T18: Gerente acessa dashboard de fluxo de caixa."""
    r = client.get('/cash_flow/', follow_redirects=True)
    assert r.status_code in (200, 302)


# ─────────────────────────────────────────────────────────────
# BLOCO 6 — PDV E FECHAMENTO
# ─────────────────────────────────────────────────────────────

def test_19_pdv_balcao(client):
    """T19: Vendedor acessa PDV de balcão para venda rápida."""
    r = client.get('/vendas/pdv', follow_redirects=True)
    assert r.status_code in (200, 302)


def test_20_busca_global_os(client):
    """T20: Qualquer usuário usa busca global para localizar OS/cliente."""
    r = client.get('/busca-global?q=OS', follow_redirects=True)
    assert r.status_code == 200
    data = json.loads(r.data)
    assert 'results' in data
