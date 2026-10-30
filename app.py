import json
import os
import sqlite3
import time
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from google import genai
from werkzeug.security import generate_password_hash, check_password_hash

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = 'automatch_chave_secreta_super_segura'

# Configuração da API do Gemini via SDK google-genai
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Configuração de uploads de mídia de perfil
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

DATABASE = os.path.join(app.root_path, 'automatch.db')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                foto_perfil TEXT
            )
        ''')
        # Garante a existência da coluna foto_perfil em bancos criados anteriormente
        try:
            conn.execute('ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT')
        except sqlite3.OperationalError:
            pass

        conn.execute('''
            CREATE TABLE IF NOT EXISTS favoritos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                carro_id TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                UNIQUE(usuario_id, carro_id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS carros_atuais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                carro_id TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                UNIQUE(usuario_id, carro_id)
            )
        ''')
        conn.commit()


init_db()


def carregar_carros():
    caminho_json = os.path.join(app.root_path, 'data', 'carros.json')
    with open(caminho_json, 'r', encoding='utf-8') as arquivo:
        return json.load(arquivo)


def get_usuario_logado():
    if 'usuario_id' in session:
        with get_db() as conn:
            user = conn.execute('SELECT * FROM usuarios WHERE id = ?', (session['usuario_id'],)).fetchone()
            if user:
                return {
                    'id': user['id'],
                    'nome': user['nome'],
                    'email': user['email'],
                    'foto_perfil': user['foto_perfil'] if 'foto_perfil' in user.keys() else None,
                    'iniciais': ''.join([n[0].upper() for n in user['nome'].split()[:2]])
                }
    return None


def get_favoritos_usuario():
    if 'usuario_id' in session:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT carro_id FROM favoritos WHERE usuario_id = ?', 
                (session['usuario_id'],)
            ).fetchall()
            return [r['carro_id'] for r in rows]
    else:
        return session.get('favoritos_anonimos', [])


def get_carros_atuais_usuario():
    if 'usuario_id' in session:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT carro_id FROM carros_atuais WHERE usuario_id = ?', 
                (session['usuario_id'],)
            ).fetchall()
            return [r['carro_id'] for r in rows]
    return []


# ================== ROTAS DE AUTENTICAÇÃO ==================

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')

        senha_hash = generate_password_hash(senha)

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)',
                    (nome, email, senha_hash)
                )
                conn.commit()
                novo_id = cursor.lastrowid
            
            session['usuario_id'] = novo_id
            session['usuario_nome'] = nome
            session['usuario_email'] = email

            favs_anonimos = session.get('favoritos_anonimos', [])
            if favs_anonimos:
                with get_db() as conn:
                    for c_id in favs_anonimos:
                        conn.execute(
                            'INSERT OR IGNORE INTO favoritos (usuario_id, carro_id) VALUES (?, ?)',
                            (novo_id, c_id)
                        )
                    conn.commit()
                session.pop('favoritos_anonimos', None)

            return redirect(url_for('visao_geral'))
        except sqlite3.IntegrityError:
            flash('Este e-mail já está cadastrado!')
            return render_template('cadastro.html')

    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        with get_db() as conn:
            user = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()

        if user and check_password_hash(user['senha_hash'], senha):
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['nome']
            session['usuario_email'] = user['email']

            favs_anonimos = session.get('favoritos_anonimos', [])
            if favs_anonimos:
                with get_db() as conn:
                    for c_id in favs_anonimos:
                        conn.execute(
                            'INSERT OR IGNORE INTO favoritos (usuario_id, carro_id) VALUES (?, ?)',
                            (user['id'], c_id)
                        )
                    conn.commit()
                session.pop('favoritos_anonimos', None)

            return redirect(url_for('visao_geral'))
        else:
            flash('E-mail ou senha incorretos.')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('visao_geral'))


# ================== APIS E INTEGRAÇÃO IA ==================

@app.route('/api/favorito/<id_carro>', methods=['POST'])
def toggle_favorito(id_carro):
    # Bloqueia a ação caso o usuário não esteja logado
    if 'usuario_id' not in session:
        return jsonify({
            'status': 'nao_autenticado',
            'mensagem': 'Você precisa estar logado para salvar veículos na garagem.',
            'redirect': url_for('login')
        }), 401

    uid = session['usuario_id']
    with get_db() as conn:
        existe = conn.execute(
            'SELECT id FROM favoritos WHERE usuario_id = ? AND carro_id = ?',
            (uid, id_carro)
        ).fetchone()

        if existe:
            conn.execute('DELETE FROM favoritos WHERE usuario_id = ? AND carro_id = ?', (uid, id_carro))
            status = "removido"
        else:
            conn.execute('INSERT INTO favoritos (usuario_id, carro_id) VALUES (?, ?)', (uid, id_carro))
            status = "adicionado"
        conn.commit()

    novos_favoritos = get_favoritos_usuario()

    return jsonify({
        'status': status,
        'carro_id': id_carro,
        'total_favoritos': len(novos_favoritos)
    })

    return jsonify({
        'status': status,
        'carro_id': id_carro,
        'total_favoritos': len(novos_favoritos)
    })


@app.route('/api/chat', methods=['POST'])
def api_chat():
    dados = request.get_json() or {}
    mensagem_usuario = dados.get('mensagem', '').strip()

    if not mensagem_usuario:
        return jsonify({'resposta': 'Por favor, digite uma mensagem.'}), 400

    carros = carregar_carros()
    resumo_catalogo = []
    
    for c in carros:
        potencia = c.get('desempenho', {}).get('potencia_cv', 'N/I')
        consumo = c.get('consumo_praticidade', {}).get('urbano_gasolina_kml', 'N/I')
        preco = c.get('preco_estimado', 0)
        
        resumo_catalogo.append(
            f"- {c['marca']} {c['modelo']} {c['versao']} ({c['ano']}): R$ {preco:,.0f} | "
            f"Potência: {potencia} cv | Consumo Urbano: {consumo} km/l | ID: {c['id']}"
        )

    instrucao_sistema = (
        "Você é o AutoMatch AI, assistente virtual inteligente especialista no catálogo do AutoMatch. "
        "Sua função é recomendar e comparar os carros com base na necessidade do usuário.\n\n"
        "REGRAS IMPORTANTES:\n"
        "1. Responda em Português do Brasil de forma clara, amigável e objetiva.\n"
        "2. Baseie suas sugestões PRIORITARIAMENTE nos carros do catálogo listados abaixo.\n"
        "3. Quando recomendar um carro, mencione o nome completo (Marca e Modelo) e o motivo da escolha.\n\n"
        "CATÁLOGO DE VEÍCULOS DISPONÍVEIS:\n" + "\n".join(resumo_catalogo)
    )

    if not ai_client:
        return jsonify({
            'resposta': 'Chave da API do Gemini não configurada. Adicione GEMINI_API_KEY no arquivo .env.'
        })

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=mensagem_usuario,
            config={
                'system_instruction': instrucao_sistema,
                'temperature': 0.7,
            }
        )
        return jsonify({'resposta': response.text})
    except Exception as e:
        print(f"Erro ao consultar Gemini: {e}")
        return jsonify({
            'resposta': 'Ocorreu um erro ao consultar o AutoMatch AI. Verifique a conexão ou tente novamente.'
        }), 500


# ================== ROTAS PRINCIPAIS ==================

@app.route('/')
@app.route('/visao-geral')
def visao_geral():
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('visao_geral.html', carros=carros, usuario=usuario, favoritos_ids=favoritos_ids)


@app.route('/catalogo')
def catalogo():
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('index.html', carros=carros, usuario=usuario, favoritos_ids=favoritos_ids)


@app.route('/carro/<id_carro>')
def detalhes(id_carro):
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carro_selecionado = next((c for c in carros if c['id'] == id_carro), None)
    if carro_selecionado:
        return render_template('detalhes.html', carro=carro_selecionado, usuario=usuario, favoritos_ids=favoritos_ids)
    return "Veículo não encontrado", 404


@app.route('/comparador')
def comparador():
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carro1_id = request.args.get('carro1', '')
    return render_template('comparador.html', carros=carros, usuario=usuario, favoritos_ids=favoritos_ids, carro1_id=carro1_id)


@app.route('/financeiro')
def financeiro():
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('financeiro.html', carros=carros, usuario=usuario, favoritos_ids=favoritos_ids)


@app.route('/formulario')
def formulario():
    carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    return render_template('formulario.html', carros=carros, usuario=usuario, favoritos_ids=favoritos_ids)


@app.route('/garagem')
def garagem():
    todos_carros = carregar_carros()
    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carros_favoritos = [c for c in todos_carros if c['id'] in favoritos_ids]
    return render_template('garagem.html', carros=carros_favoritos, usuario=usuario, favoritos_ids=favoritos_ids)


@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario = get_usuario_logado()
    favoritos_ids = get_favoritos_usuario()
    carros_atuais_ids = get_carros_atuais_usuario()
    todos_carros = carregar_carros()

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'atualizar_dados':
            novo_nome = request.form.get('nome')
            novo_email = request.form.get('email')
            foto_file = request.files.get('foto_perfil')
            nome_foto = usuario['foto_perfil']

            if foto_file and foto_file.filename != '' and allowed_file(foto_file.filename):
                ext = foto_file.filename.rsplit('.', 1)[1].lower()
                nome_foto = f"avatar_user_{session['usuario_id']}_{int(time.time())}.{ext}"
                caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_foto)
                foto_file.save(caminho)

            try:
                with get_db() as conn:
                    conn.execute(
                        'UPDATE usuarios SET nome = ?, email = ?, foto_perfil = ? WHERE id = ?',
                        (novo_nome, novo_email, nome_foto, session['usuario_id'])
                    )
                    conn.commit()
                session['usuario_nome'] = novo_nome
                session['usuario_email'] = novo_email
                flash('Perfil atualizado com sucesso!')
            except sqlite3.IntegrityError:
                flash('Este e-mail já está em uso por outra conta.')

        elif acao == 'alterar_senha':
            senha_atual = request.form.get('senha_atual')
            nova_senha = request.form.get('nova_senha')
            with get_db() as conn:
                user = conn.execute(
                    'SELECT senha_hash FROM usuarios WHERE id = ?',
                    (session['usuario_id'],)
                ).fetchone()

                if user and check_password_hash(user['senha_hash'], senha_atual):
                    nova_hash = generate_password_hash(nova_senha)
                    conn.execute(
                        'UPDATE usuarios SET senha_hash = ? WHERE id = ?',
                        (nova_hash, session['usuario_id'])
                    )
                    conn.commit()
                    flash('Senha alterada com sucesso!')
                else:
                    flash('A senha atual informada está incorreta.')

        elif acao == 'adicionar_carro_atual':
            carro_id = request.form.get('carro_id')
            if carro_id:
                with get_db() as conn:
                    conn.execute(
                        'INSERT OR IGNORE INTO carros_atuais (usuario_id, carro_id) VALUES (?, ?)',
                        (session['usuario_id'], carro_id)
                    )
                    conn.commit()
                flash('Carro atual adicionado com sucesso!')

        elif acao == 'remover_carro_atual':
            carro_id = request.form.get('carro_id')
            if carro_id:
                with get_db() as conn:
                    conn.execute(
                        'DELETE FROM carros_atuais WHERE usuario_id = ? AND carro_id = ?',
                        (session['usuario_id'], carro_id)
                    )
                    conn.commit()
                flash('Carro removido com sucesso.')

        return redirect(url_for('perfil'))

    objetos_carros_atuais = [c for c in todos_carros if c['id'] in carros_atuais_ids]

    return render_template(
        'perfil.html', 
        usuario=usuario, 
        favoritos_ids=favoritos_ids,
        carros_atuais=objetos_carros_atuais,
        todos_carros=todos_carros
    )


if __name__ == '__main__':
    app.run(debug=True)