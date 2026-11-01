import os
import json
import sqlite3
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'automatch-chave-secreta-dev-2026')

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    from google import genai
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
except Exception as e:
    client = None

DB_PATH = 'automatch.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                foto_perfil TEXT,
                carro_atual_id TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS favoritos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                carro_id TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                UNIQUE(usuario_id, carro_id)
            )
        ''')
        conn.commit()

init_db()

# Registra o filtro customizado no Jinja2 para substituir o .format() que quebrava a página
@app.template_filter('formata_preco')
def formata_preco(valor):
    try:
        val = float(valor)
        return f"{val:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return "0"

def carregar_carros():
    json_path = os.path.join('data', 'carros.json')
    if not os.path.exists(json_path):
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            carros = json.load(f)
    except Exception as e:
        print(f"Erro ao carregar JSON: {e}")
        return []

    # Sanitiza os dados garantindo que o Jinja2 nunca encontre valores None
    if isinstance(carros, list):
        for c in carros:
            if not isinstance(c, dict):
                continue
            c.setdefault('preco_estimado', 0)
            if 'desempenho' not in c or not isinstance(c['desempenho'], dict):
                c['desempenho'] = {}
            c['desempenho'].setdefault('potencia_cv', 'N/I')
            
            if 'consumo_praticidade' not in c or not isinstance(c['consumo_praticidade'], dict):
                c['consumo_praticidade'] = {}
            c['consumo_praticidade'].setdefault('urbano_gasolina_kml', 'N/I')
            
            if 'media' not in c or not isinstance(c['media'], dict):
                c['media'] = {}
            c['media'].setdefault('imagem_principal', '')

    return carros

def get_usuario_logado():
    user_id = session.get('usuario_id')
    if not user_id:
        return None
    with get_db() as conn:
        user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user:
            u_dict = dict(user)
            partes = u_dict.get('nome', 'Usuário').split()
            iniciais = partes[0][0].upper() if partes else 'U'
            if len(partes) > 1:
                iniciais += partes[-1][0].upper()
            u_dict['iniciais'] = iniciais
            return u_dict
    return None

def get_favoritos_usuario():
    user_id = session.get('usuario_id')
    if not user_id:
        return []
    with get_db() as conn:
        rows = conn.execute('SELECT carro_id FROM favoritos WHERE usuario_id = ?', (user_id,)).fetchall()
        return [r['carro_id'] for r in rows]

@app.route('/', endpoint='index')
@app.route('/catalogo', endpoint='catalogo')
def index():
    carros = carregar_carros()
    if carros:
        random.shuffle(carros)
    
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    
    return render_template(
        'index.html', 
        carros=carros, 
        usuario=usuario, 
        favoritos_ids=favoritos_ids
    )

@app.route('/visao_geral')
def visao_geral():
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carros = carregar_carros()
    return render_template('visao_geral.html', usuario=usuario, favoritos_ids=favoritos_ids, carros=carros)

@app.route('/carro/<carro_id>')
def detalhes_carro(carro_id):
    carros = carregar_carros()
    carro = next((c for c in carros if c['id'] == carro_id), None)
    if not carro:
        return redirect(url_for('index'))
    
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('detalhes.html', carro=carro, usuario=usuario, favoritos_ids=favoritos_ids)

@app.route('/comparador')
def comparador():
    carros = carregar_carros()
    carro1_id = request.args.get('carro1', '')
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('comparador.html', carros=carros, carro1_id=carro1_id, usuario=usuario, favoritos_ids=favoritos_ids)

@app.route('/financeiro')
def financeiro():
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carros = carregar_carros()
    return render_template('financeiro.html', usuario=usuario, favoritos_ids=favoritos_ids, carros=carros)

@app.route('/formulario')
def formulario():
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carros = carregar_carros()
    return render_template('formulario.html', usuario=usuario, favoritos_ids=favoritos_ids, carros=carros)

@app.route('/garagem')
def garagem():
    usuario = get_usuario_logado()
    if not usuario:
        return redirect(url_for('login'))
    
    favoritos_ids = get_favoritos_usuario()
    todos_carros = carregar_carros()
    carros_favoritos = [c for c in todos_carros if c['id'] in favoritos_ids]
    
    return render_template('garagem.html', usuario=usuario, favoritos_ids=favoritos_ids, carros=carros_favoritos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()
        
        with get_db() as conn:
            user = conn.execute('SELECT * FROM usuarios WHERE email = ? AND senha = ?', (email, senha)).fetchone()
            if user:
                session['usuario_id'] = user['id']
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('index'))
            else:
                flash('E-mail ou senha incorretos.', 'danger')
                
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()
        
        with get_db() as conn:
            user_exist = conn.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone()
            if user_exist:
                flash('Este e-mail já está cadastrado.', 'danger')
            else:
                cursor = conn.execute('INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)', (nome, email, senha))
                conn.commit()
                session['usuario_id'] = cursor.lastrowid
                flash('Conta criada com sucesso!', 'success')
                return redirect(url_for('index'))
                
    return render_template('cadastro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    usuario = get_usuario_logado()
    if not usuario:
        return redirect(url_for('login'))
        
    carros = carregar_carros()
    favoritos_ids = get_favoritos_usuario()

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        carro_atual_id = request.form.get('carro_atual_id', '').strip()
        nova_senha = request.form.get('nova_senha', '').strip()

        foto_filename = usuario.get('foto_perfil')
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '':
                filename = secure_filename(f"user_{usuario['id']}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_filename = filename

        with get_db() as conn:
            if nova_senha:
                conn.execute('''
                    UPDATE usuarios 
                    SET nome = ?, email = ?, carro_atual_id = ?, foto_perfil = ?, senha = ?
                    WHERE id = ?
                ''', (nome, email, carro_atual_id, foto_filename, nova_senha, usuario['id']))
            else:
                conn.execute('''
                    UPDATE usuarios 
                    SET nome = ?, email = ?, carro_atual_id = ?, foto_perfil = ?
                    WHERE id = ?
                ''', (nome, email, carro_atual_id, foto_filename, usuario['id']))
            conn.commit()

        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('perfil'))

    return render_template('perfil.html', usuario=usuario, carros=carros, favoritos_ids=favoritos_ids)

@app.route('/api/favorito/<carro_id>', methods=['POST'])
def toggle_favorito(carro_id):
    user_id = session.get('usuario_id')
    if not user_id:
        return jsonify({'error': 'Não autenticado'}), 401
        
    with get_db() as conn:
        fav = conn.execute('SELECT id FROM favoritos WHERE usuario_id = ? AND carro_id = ?', (user_id, carro_id)).fetchone()
        if fav:
            conn.execute('DELETE FROM favoritos WHERE id = ?', (fav['id'],))
            status = 'removido'
        else:
            conn.execute('INSERT INTO favoritos (usuario_id, carro_id) VALUES (?, ?)', (user_id, carro_id))
            status = 'adicionado'
        conn.commit()
        
        total = conn.execute('SELECT COUNT(*) as count FROM favoritos WHERE usuario_id = ?', (user_id,)).fetchone()['count']

    return jsonify({'status': status, 'total_favoritos': total})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    mensagem_usuario = data.get('mensagem', '').strip()
    
    if not mensagem_usuario:
        return jsonify({'resposta': 'Por favor, digite uma mensagem.'})

    if not client:
        return jsonify({'resposta': 'Erro: A chave GEMINI_API_KEY não foi configurada no servidor.'})

    carros = carregar_carros()
    contexto_carros = json.dumps(carros[:25], ensure_ascii=False)

    system_prompt = f"""
    Você é o AutoMatch AI, um assistente especializado em recomendação automotiva do sistema AutoMatch.
    Responda de forma clara, amigável, direta e em português do Brasil.
    Utilize os seguintes dados de veículos do catálogo como referência:
    {contexto_carros}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nUsuário: {mensagem_usuario}"
        )
        resposta_texto = response.text if response.text else "Não consegui processar sua solicitação no momento."
        return jsonify({'resposta': resposta_texto})
    except Exception as e:
        print("Erro na API Gemini:", e)
        return jsonify({'resposta': 'Desculpe, ocorreu um erro ao consultar o assistente de IA. Tente novamente em instantes.'})

import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)