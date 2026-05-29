from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sys
import os
from werkzeug.utils import secure_filename

# Adicionar o diretório pai ao caminho de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar o módulo de banco de dados
from database import get_db
from utils.auth import login_required

# Criar um Blueprint para as rotas de empresa
company_bp = Blueprint('company', __name__)

# Configurações de upload
UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads', 'logos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

# Criar pasta de upload se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =====================================================
# ROTAS DE CONFIGURAÇÃO DA EMPRESA
# =====================================================

@company_bp.route('/empresa/configuracoes', methods=['GET'])
@login_required
def company_settings():
    """Exibe as configurações da empresa."""
    db = get_db()
    
    # Buscar configurações da empresa
    company = db.fetch_one("""
        SELECT * FROM company_settings
        ORDER BY id DESC
        LIMIT 1
    """)
    
    # Se não existir, criar registro padrão
    if not company:
        db.execute("""
            INSERT INTO company_settings (company_name, legal_name)
            VALUES ('Minha Empresa', 'Minha Empresa LTDA')
        """)
        db.connection.commit()
        
        company = db.fetch_one("""
            SELECT * FROM company_settings
            ORDER BY id DESC
            LIMIT 1
        """)
    
    return render_template('company_settings.html', company=company)

@company_bp.route('/empresa/configuracoes', methods=['POST'])
@login_required
def company_settings_save():
    """Salva as configurações da empresa."""
    db = get_db()
    
    # Obter dados do formulário
    company_name = request.form.get('company_name', '').strip()
    legal_name = request.form.get('legal_name', '').strip()
    cnpj = request.form.get('cnpj', '').strip()
    ie = request.form.get('ie', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    website = request.form.get('website', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    zip_code = request.form.get('zip_code', '').strip()
    country = request.form.get('country', 'Brasil').strip()
    
    # Validação básica
    if not company_name:
        flash('Nome da empresa é obrigatório!', 'danger')
        return redirect(url_for('company.company_settings'))
    
    # Buscar configuração existente
    existing = db.fetch_one("SELECT id FROM company_settings LIMIT 1")
    
    if existing:
        # Atualizar
        db.execute("""
            UPDATE company_settings SET
                company_name = %s,
                legal_name = %s,
                cnpj = %s,
                ie = %s,
                phone = %s,
                email = %s,
                website = %s,
                address = %s,
                city = %s,
                state = %s,
                zip_code = %s,
                country = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (company_name, legal_name, cnpj, ie, phone, email, website,
              address, city, state, zip_code, country, existing['id']))
    else:
        # Inserir novo
        db.execute("""
            INSERT INTO company_settings (
                company_name, legal_name, cnpj, ie, phone, email, website,
                address, city, state, zip_code, country
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (company_name, legal_name, cnpj, ie, phone, email, website,
              address, city, state, zip_code, country))
    
    db.connection.commit()
    flash('Configurações da empresa salvas com sucesso!', 'success')
    return redirect(url_for('company.company_settings'))

@company_bp.route('/empresa/upload-logo', methods=['POST'])
@login_required
def upload_logo():
    """Faz upload da logo da empresa."""
    db = get_db()
    
    # Verificar se foi enviado um arquivo
    if 'logo' not in request.files:
        flash('Nenhum arquivo selecionado!', 'danger')
        return redirect(url_for('company.company_settings'))
    
    file = request.files['logo']
    
    # Verificar se o arquivo tem um nome
    if file.filename == '':
        flash('Nenhum arquivo selecionado!', 'danger')
        return redirect(url_for('company.company_settings'))
    
    # Verificar se é um arquivo permitido
    if file and allowed_file(file.filename):
        # Gerar nome seguro
        filename = secure_filename(file.filename)
        
        # Adicionar timestamp para evitar sobrescrever
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        filename = f"logo_{timestamp}{ext}"
        
        # Salvar arquivo
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Caminho relativo para o banco
        logo_path = f"uploads/logos/{filename}"
        
        # Atualizar banco de dados
        company = db.fetch_one("SELECT id FROM company_settings LIMIT 1")
        
        if company:
            db.execute("""
                UPDATE company_settings
                SET logo_path = %s, updated_at = NOW()
                WHERE id = %s
            """, (logo_path, company['id']))
        else:
            db.execute("""
                INSERT INTO company_settings (company_name, logo_path)
                VALUES ('Minha Empresa', %s)
            """, (logo_path,))
        
        db.connection.commit()
        flash('Logo enviada com sucesso!', 'success')
    else:
        flash('Formato de arquivo não permitido! Use PNG, JPG, JPEG, GIF, WEBP ou SVG.', 'danger')
    
    return redirect(url_for('company.company_settings'))

@company_bp.route('/empresa/remover-logo', methods=['POST'])
@login_required
def remove_logo():
    """Remove a logo da empresa."""
    db = get_db()
    
    # Buscar logo atual
    company = db.fetch_one("SELECT logo_path FROM company_settings LIMIT 1")
    
    if company and company['logo_path']:
        # Tentar remover arquivo físico
        try:
            filepath = os.path.join('app', 'static', company['logo_path'])
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Erro ao remover arquivo: {e}")
        
        # Remover do banco
        db.execute("""
            UPDATE company_settings
            SET logo_path = NULL, updated_at = NOW()
            WHERE id = %s
        """, (company['id'],))
        db.connection.commit()
        
        flash('Logo removida com sucesso!', 'success')
    else:
        flash('Nenhuma logo para remover.', 'info')
    
    return redirect(url_for('company.company_settings'))
