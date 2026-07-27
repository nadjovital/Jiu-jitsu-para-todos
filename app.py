from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jiujitsu-todo-chave-secreta-2026-muito-segura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jiujitsu_todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    faixa = db.Column(db.String(50), default='Branca')
    graus = db.Column(db.Integer, default=0)
    data_ultima_graduacao = db.Column(db.Date, nullable=True)
    data_nascimento = db.Column(db.Date, nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    historico = db.relationship('HistoricoGraduacao', backref='aluno', lazy=True, foreign_keys='HistoricoGraduacao.aluno_id')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def is_diretor(self):
        return self.role == 'diretor'

    def is_professor(self):
        return self.role == 'professor'

    def is_aluno(self):
        return self.role == 'aluno'

    def idade(self):
        if not self.data_nascimento:
            return None
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - ((hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day))

    def faixa_completa(self):
        if self.graus > 0:
            return f"{self.faixa} ({self.graus}º grau)"
        return self.faixa

class HistoricoGraduacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    faixa_anterior = db.Column(db.String(50))
    graus_anterior = db.Column(db.Integer)
    faixa_nova = db.Column(db.String(50), nullable=False)
    graus_novo = db.Column(db.Integer, default=0)
    data_graduacao = db.Column(db.Date, nullable=False, default=date.today)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    professor = db.relationship('Usuario', foreign_keys=[professor_id])

FAIXAS_ADULTOS = ['Branca', 'Azul', 'Roxa', 'Marrom', 'Preta', 'Coral (Vermelha e Preta)', 'Coral (Vermelha e Branca)', 'Vermelha']
FAIXAS_INFANTIS = ['Branca', 'Cinza e Branca', 'Cinza', 'Cinza e Preta', 'Amarela e Branca', 'Amarela', 'Amarela e Preta', 'Laranja e Branca', 'Laranja', 'Laranja e Preta', 'Verde e Branca', 'Verde', 'Verde e Preta']
ORDEM_ADULTOS = {faixa: i for i, faixa in enumerate(FAIXAS_ADULTOS)}
ORDEM_INFANTIS = {faixa: i for i, faixa in enumerate(FAIXAS_INFANTIS)}

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para continuar.', 'warning')
                return redirect(url_for('login'))
            user = Usuario.query.get(session['user_id'])
            if not user or user.role not in roles:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

def get_current_user():
    if 'user_id' in session:
        return Usuario.query.get(session['user_id'])
    return None

def pode_promover(promotor, aluno):
    if not promotor or not aluno:
        return False
    if promotor.is_diretor():
        return True
    if promotor.is_professor() and aluno.is_aluno():
        return True
    return False

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        cpf = request.form.get('cpf', '').strip()
        senha = request.form.get('senha', '')
        user = Usuario.query.filter_by(cpf=cpf, ativo=True).first()
        if user and user.check_senha(senha):
            session['user_id'] = user.id
            session['role'] = user.role
            flash(f'Bem-vindo(a), {user.nome}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('CPF ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if user.is_diretor():
        total_alunos = Usuario.query.filter_by(role='aluno', ativo=True).count()
        total_professores = Usuario.query.filter_by(role='professor', ativo=True).count()
        recentes = Usuario.query.filter_by(role='aluno').order_by(Usuario.data_cadastro.desc()).limit(5).all()
        return render_template('dashboard_diretor.html', user=user, total_alunos=total_alunos, total_professores=total_professores, recentes=recentes)
    elif user.is_professor():
        meus_alunos = Usuario.query.filter_by(role='aluno', ativo=True).order_by(Usuario.nome).all()
        return render_template('dashboard_professor.html', user=user, alunos=meus_alunos)
    else:
        historico = HistoricoGraduacao.query.filter_by(aluno_id=user.id).order_by(HistoricoGraduacao.data_graduacao.desc()).all()
        return render_template('dashboard_aluno.html', user=user, historico=historico)

@app.route('/alunos/novo', methods=['GET', 'POST'])
@role_required('diretor', 'professor')
def novo_aluno():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cpf = request.form.get('cpf', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        data_nasc = request.form.get('data_nascimento')
        telefone = request.form.get('telefone', '').strip()
        faixa = request.form.get('faixa', 'Branca')
        graus = int(request.form.get('graus', 0) or 0)
        if not nome or not cpf or not email or not senha:
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for('novo_aluno'))
        if Usuario.query.filter_by(cpf=cpf).first():
            flash('CPF já cadastrado.', 'danger')
            return redirect(url_for('novo_aluno'))
        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
            return redirect(url_for('novo_aluno'))
        aluno = Usuario(nome=nome, cpf=cpf, email=email, role='aluno', faixa=faixa, graus=graus, telefone=telefone, professor_id=session['user_id'], data_ultima_graduacao=date.today() if faixa != 'Branca' else None)
        aluno.set_senha(senha)
        if data_nasc:
            try:
                aluno.data_nascimento = datetime.strptime(data_nasc, '%Y-%m-%d').date()
            except:
                pass
        db.session.add(aluno)
        db.session.commit()
        hist = HistoricoGraduacao(aluno_id=aluno.id, faixa_anterior=None, graus_anterior=0, faixa_nova=faixa, graus_novo=graus, data_graduacao=date.today(), professor_id=session['user_id'], observacao='Cadastro inicial')
        db.session.add(hist)
        db.session.commit()
        flash(f'Aluno {nome} cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_alunos'))
    faixas = FAIXAS_ADULTOS + [f for f in FAIXAS_INFANTIS if f not in FAIXAS_ADULTOS]
    return render_template('novo_aluno.html', faixas=faixas, user=get_current_user())

@app.route('/alunos')
@role_required('diretor', 'professor')
def listar_alunos():
    alunos = Usuario.query.filter_by(role='aluno', ativo=True).order_by(Usuario.nome).all()
    return render_template('listar_alunos.html', alunos=alunos, user=get_current_user())

@app.route('/alunos/<int:id>')
@login_required
def ver_aluno(id):
    aluno = Usuario.query.get_or_404(id)
    user = get_current_user()
    if user.is_aluno() and user.id != aluno.id:
        flash('Acesso negado.', 'danger')
