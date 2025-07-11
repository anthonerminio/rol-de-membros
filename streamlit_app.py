import streamlit as st
import pandas as pd
import gspread
import json
import os
import re
import requests
from datetime import datetime, date
from fpdf import FPDF
from io import BytesIO
from streamlit_oauth import OAuth2Component
import jwt

# --- 1) Configuração da página (DEVE SER O PRIMEIRO COMANDO STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Fichário de Membros PIB Gaibu")

# --- A) Parâmetros de Login Google (lendo dos Segredos) ---
try:
    GOOGLE_CLIENT_ID = st.secrets["google_oauth"]["client_id"]
    GOOGLE_CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
    GOOGLE_REDIRECT_URI = "https://pibgaibu.streamlit.app"
    EMAILS_PERMITIDOS = {
        "antonio.esn01@gmail.com",
        "neto1999.legal@gmail.com",
        "adrielsoliveira1907@gmail.com"
    }
    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token"
    )
except (KeyError, FileNotFoundError):
    # Este bloco só será executado se os segredos não estiverem configurados
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()


# --- Funções Auxiliares ---
def criar_pdf(df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 10)
    cols = df.columns
    col_widths = {'Selecionar': 25, 'Nome': 60, 'CPF': 30, 'Status': 20}
    line_height = pdf.font_size * 2.5
    for col in cols:
        width = col_widths.get(col, 28)
        pdf.cell(width, line_height, col, border=1, ln=0, align='C')
    pdf.ln(line_height)
    pdf.set_font('helvetica', '', 9)
    for index, row in df.iterrows():
        for col in cols:
            width = col_widths.get(col, 28)
            text = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(width, line_height, text, border=1, ln=0, align='L')
        pdf.ln(line_height)
    return bytes(pdf.output(dest='S'))

# --- Funções de Dados (Google Sheets) ---
NOME_PLANILHA = "Fichario_Membros_PIB_Gaibu"
NOME_ABA = "Membros"

try:
    creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
    creds_dict = json.loads(creds_json_str)
except (KeyError, FileNotFoundError):
    st.error("As credenciais do Google Sheets não foram encontradas. Por favor, configure os segredos.")
    st.stop()

@st.cache_resource(ttl=3600)
def get_client(creds):
    return gspread.service_account_from_dict(creds)

gc = get_client(creds_dict)

HEADERS = [
    "Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao",
    "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)",
    "Nome do Pai", "Nome da Mae", "Cônjuge", "CEP", "Endereco", "Bairro",
    "Cidade", "UF (Endereco)", "Grau de Instrucao", "Celular",
    "Data de Conversao", "Data de Admissao", "Status", "Observações"
]

def carregar_membros():
    # ... (código da função inalterado)
    return []

def salvar_membros(lista):
    # ... (código da função inalterado)
    pass

def formatar_datas(df, colunas):
    # ... (código da função inalterado)
    return df

def buscar_cep(cep):
    # ... (código da função inalterado)
    return None

# Inicializa o estado da sessão
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- LÓGICA PRINCIPAL DE EXIBIÇÃO ---

# Se não estiver autenticado, mostra a tela de login
if not st.session_state.authenticated:
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True)
        st.markdown("---")
        token = oauth2.authorize_button(
            "Entrar com Google",
            key="google_login",
            redirect_uri=GOOGLE_REDIRECT_URI,
            scope="openid email profile"
        )
        if token:
            try:
                id_token = token.get("id_token")
                if id_token and isinstance(id_token, str):
                    user_info = jwt.decode(id_token.encode(), options={"verify_signature": False})
                    email = user_info.get("email", "")
                    if email in EMAILS_PERMITIDOS:
                        st.session_state.authenticated = True
                        st.session_state.username = email
                        st.rerun()
                    else:
                        st.error("Acesso não autorizado para este e-mail.")
                else:
                    st.error("Resposta de autenticação inválida recebida do Google.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o login: {e}")
# Se estiver autenticado, mostra a aplicação principal
else:
    # Inicializa o resto do estado da sessão apenas uma vez após o login
    if "membros" not in st.session_state:
        st.session_state.membros = carregar_membros()
        # ... outras inicializações ...

    _, col_content = st.columns([1, 1])
    with col_content:
        col_bem_vindo, col_logout = st.columns([3, 1])
        with col_bem_vindo:
            st.markdown(f"<p style='text-align: right; padding-top: 8px;'>Bem-vindo(a), <strong>{st.session_state.get('username', '')}</strong>!</p>", unsafe_allow_html=True)
        with col_logout:
            if st.button("Sair"):
                st.session_state.authenticated = False
                st.session_state.username = ""
                st.rerun()
    st.markdown("---")
    
    # Resto da sua aplicação (abas, formulários, etc.)
    tab1, tab2, tab3 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir"])
    # ... Coloque aqui o código das suas abas ...import streamlit as st
import pandas as pd
import gspread
import json
import os
import re
import requests
from datetime import datetime, date
from fpdf import FPDF
from io import BytesIO
from streamlit_oauth import OAuth2Component
import jwt

# --- 1) Configuração da página (DEVE SER O PRIMEIRO COMANDO STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Fichário de Membros PIB Gaibu")

# --- A) Parâmetros de Login Google (lendo dos Segredos) ---
try:
    GOOGLE_CLIENT_ID = st.secrets["google_oauth"]["client_id"]
    GOOGLE_CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
    GOOGLE_REDIRECT_URI = "https://pibgaibu.streamlit.app"
    EMAILS_PERMITIDOS = {
        "antonio.esn01@gmail.com",
        "neto1999.legal@gmail.com",
        "adrielsoliveira1907@gmail.com"
    }
    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token"
    )
except (KeyError, FileNotFoundError):
    # Este bloco só será executado se os segredos não estiverem configurados
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()


# --- Funções Auxiliares ---
def criar_pdf(df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 10)
    cols = df.columns
    col_widths = {'Selecionar': 25, 'Nome': 60, 'CPF': 30, 'Status': 20}
    line_height = pdf.font_size * 2.5
    for col in cols:
        width = col_widths.get(col, 28)
        pdf.cell(width, line_height, col, border=1, ln=0, align='C')
    pdf.ln(line_height)
    pdf.set_font('helvetica', '', 9)
    for index, row in df.iterrows():
        for col in cols:
            width = col_widths.get(col, 28)
            text = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(width, line_height, text, border=1, ln=0, align='L')
        pdf.ln(line_height)
    return bytes(pdf.output(dest='S'))

# --- Funções de Dados (Google Sheets) ---
NOME_PLANILHA = "Fichario_Membros_PIB_Gaibu"
NOME_ABA = "Membros"

try:
    creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
    creds_dict = json.loads(creds_json_str)
except (KeyError, FileNotFoundError):
    st.error("As credenciais do Google Sheets não foram encontradas. Por favor, configure os segredos.")
    st.stop()

@st.cache_resource(ttl=3600)
def get_client(creds):
    return gspread.service_account_from_dict(creds)

gc = get_client(creds_dict)

HEADERS = [
    "Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao",
    "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)",
    "Nome do Pai", "Nome da Mae", "Cônjuge", "CEP", "Endereco", "Bairro",
    "Cidade", "UF (Endereco)", "Grau de Instrucao", "Celular",
    "Data de Conversao", "Data de Admissao", "Status", "Observações"
]

def carregar_membros():
    # ... (código da função inalterado)
    return []

def salvar_membros(lista):
    # ... (código da função inalterado)
    pass

def formatar_datas(df, colunas):
    # ... (código da função inalterado)
    return df

def buscar_cep(cep):
    # ... (código da função inalterado)
    return None

# Inicializa o estado da sessão
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- LÓGICA PRINCIPAL DE EXIBIÇÃO ---

# Se não estiver autenticado, mostra a tela de login
if not st.session_state.authenticated:
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True)
        st.markdown("---")
        token = oauth2.authorize_button(
            "Entrar com Google",
            key="google_login",
            redirect_uri=GOOGLE_REDIRECT_URI,
            scope="openid email profile"
        )
        if token:
            try:
                id_token = token.get("id_token")
                if id_token and isinstance(id_token, str):
                    user_info = jwt.decode(id_token.encode(), options={"verify_signature": False})
                    email = user_info.get("email", "")
                    if email in EMAILS_PERMITIDOS:
                        st.session_state.authenticated = True
                        st.session_state.username = email
                        st.rerun()
                    else:
                        st.error("Acesso não autorizado para este e-mail.")
                else:
                    st.error("Resposta de autenticação inválida recebida do Google.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o login: {e}")
# Se estiver autenticado, mostra a aplicação principal
else:
    # Inicializa o resto do estado da sessão apenas uma vez após o login
    if "membros" not in st.session_state:
        st.session_state.membros = carregar_membros()
        # ... outras inicializações ...

    _, col_content = st.columns([1, 1])
    with col_content:
        col_bem_vindo, col_logout = st.columns([3, 1])
        with col_bem_vindo:
            st.markdown(f"<p style='text-align: right; padding-top: 8px;'>Bem-vindo(a), <strong>{st.session_state.get('username', '')}</strong>!</p>", unsafe_allow_html=True)
        with col_logout:
            if st.button("Sair"):
                st.session_state.authenticated = False
                st.session_state.username = ""
                st.rerun()
    st.markdown("---")
    
    # Resto da sua aplicação (abas, formulários, etc.)
    tab1, tab2, tab3 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir"])
    # ... Coloque aqui o código das suas abas ...
