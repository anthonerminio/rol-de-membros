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
import jwt # <-- 1. NOVA IMPORTAÇÃO

# --- 1) Configuração da página ---
st.set_page_config(layout="wide", page_title="Fichário de Membros PIB Gaibu")

# --- A) Parâmetros de Login Google (lendo dos Segredos) ---
GOOGLE_CLIENT_ID = st.secrets["google_oauth"]["client_id"]
GOOGLE_CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
GOOGLE_REDIRECT_URI = "https://pibgaibu.streamlit.app"  # SUA URL PÚBLICA
EMAILS_PERMITIDOS = {"antonio.esn01@gmail.com", "neto1999.legal@gmail.com", "adrielsoliveira1907@gmail.com"}

oauth2 = OAuth2Component(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
    token_endpoint="https://oauth2.googleapis.com/token"
)

# --- Função para Gerar PDF ---
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

# --- 2) Parâmetros Google Sheets e Funções de Dados ---
NOME_PLANILHA = "Fichario_Membros_PIB_Gaibu"
NOME_ABA = "Membros"

# Carrega as credenciais do Google Sheets a partir dos Segredos
creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
creds_dict = json.loads(creds_json_str)

@st.cache_resource(ttl=3600)
def get_client(creds):
    return gspread.service_account_from_dict(creds)

gc = get_client(creds_dict)

def carregar_membros():
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(NOME_PLANILHA)
        ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols="25")
        headers = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "..."]
        ws.insert_row(headers, 1)
        return []
    except gspread.WorksheetNotFound:
        sh = gc.open(NOME_PLANILHA)
        ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols="25")
        headers = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "..."]
        ws.insert_row(headers, 1)
        return []
    return ws.get_all_records()

def salvar_membros(lista):
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear()
        col_order = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "..."]
        ws.insert_row(col_order, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in col_order] for m in lista]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        else:
            st.info("Nenhum dado para salvar; planilha limpa.")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def formatar_datas(df, colunas):
    for col in colunas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
    return df

def buscar_cep(cep):
    cep = re.sub(r"[^\d]", "", cep)
    if len(cep) != 8: return None
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
        if resp.status_code == 200:
            data = resp.json()
            if "erro" not in data:
                return {"endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(), "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf": data.get("uf", "")}
    except Exception:
        pass
    return None

def init_state():
    if "inicializado" not in st.session_state:
        st.session_state.inicializado = True
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.membros = carregar_membros()
        st.session_state.cep_busca_ok = False
        st.session_state.confirmando_exclusao = False
        st.session_state.cpfs_para_excluir = set()
        for key in ["nome", "cpf", "estado_civil", "profissao", "forma_admissao", "nacionalidade", "naturalidade", "uf_nat", "nome_pai", "nome_mae", "conjuge", "cep", "endereco", "bairro", "cidade", "..."]:
            st.session_state[key] = ""
        st.session_state["sexo"] = "M"
        st.session_state["data_nasc"] = None
        st.session_state["data_conv"] = None
        st.session_state["data_adm"] = None

# --- C) Lógica Principal de Exibição ---
init_state()

if not st.session_state.get("authenticated", False):
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
        # ALTERAÇÃO: Checagem robusta do token
        if isinstance(token, dict) and "id_token" in token:
            try:
                id_token = token.get("id_token")
                # Decodifica o token para obter as informações do usuário
                user_info = jwt.decode(id_token, options={"verify_signature": False})
                email = user_info.get("email", "")

                if email in EMAILS_PERMITIDOS:
                    st.session_state.authenticated = True
                    st.session_state.username = email
                    st.rerun()
                else:
                    st.error("Acesso não autorizado para este e-mail.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o login: {e}")
        elif token is not None:
            st.error("Resposta de autenticação inesperada. Tente novamente ou contate o suporte.")

else:
    # O resto do código da aplicação permanece inalterado
    _, col_content = st.columns([1, 1])
    with col_content:
        col_bem_vindo, col_logout = st.columns([3, 1])
        with col_bem_vindo:
            st.markdown(f"<p style='text-align: right; padding-top: 8px;'>Bem-vindo(a), <strong>{st.session_state.username}</strong>!</p>", unsafe_allow_html=True)
        with col_logout:
            if st.button("Sair"):
                st.session_state.authenticated = False
                st.session_state.username = ""
                st.rerun()
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir"])

    # ... (demais abas e funcionalidades iguais ao seu código original)
