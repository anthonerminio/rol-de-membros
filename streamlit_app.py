# Versão Final e Completa - v4.7
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

# --- 1) Configuração da página ---
st.set_page_config(layout="wide", page_title="Fichário de Membros v4.7")

# --- A) Parâmetros de Login Google ---
try:
    GOOGLE_CLIENT_ID = st.secrets["google_oauth"]["client_id"]
    GOOGLE_CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
    GOOGLE_REDIRECT_URI = "https://pibgaibu.streamlit.app"
    EMAILS_PERMITIDOS = {"antonio.esn01@gmail.com", "neto1999.legal@gmail.com", "adrielsoliveira1907@gmail.com"}

    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token"
    )
except (KeyError, FileNotFoundError):
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit.")
    st.stop()


# --- Funções Auxiliares de Exportação ---
def criar_pdf_lista(df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=8)
    
    cols = df.columns
    col_widths = {'Nome': 45, 'CPF': 25, 'Data de Nascimento': 22, 'Celular': 25, 'Estado Civil': 22, 'Profissão': 25}
    line_height = pdf.font_size * 2.5
    
    pdf.set_font_size(10)
    for col in cols:
        width = col_widths.get(col, 18)
        pdf.cell(width, line_height, col, border=1, ln=0, align='C')
    pdf.ln(line_height)
    
    pdf.set_font_size(7)
    for index, row in df.iterrows():
        for col in cols:
            width = col_widths.get(col, 18)
            pdf.cell(width, line_height, str(row[col]), border=1, ln=0, align='L')
        pdf.ln(line_height)
    return bytes(pdf.output())

def criar_pdf_aniversariantes(df, mes_nome):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=16)

    pdf.cell(0, 10, f'Aniversariantes de {mes_nome}', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('DejaVu', size=12)
    pdf.cell(130, 10, 'Nome Completo', 1, 0, 'C')
    pdf.cell(60, 10, 'Data de Nascimento', 1, 1, 'C')
    pdf.set_font('DejaVu', size=11)
    for index, row in df.iterrows():
        pdf.cell(130, 10, str(row['Nome Completo']), 1, 0, 'L')
        pdf.cell(60, 10, str(row['Data de Nascimento Completa']), 1, 1, 'C')
    return bytes(pdf.output())

def criar_pdf_ficha(membro):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=16)
    
    pdf.cell(0, 10, 'Ficha Individual de Membro - PIB Gaibu', 0, 1, 'C')
    pdf.set_font("DejaVu", size=14)
    pdf.cell(0, 10, membro.get("Nome", ""), 0, 1, 'C')
    pdf.ln(5)

    def draw_field(label, value):
        if value and str(value).strip():
            pdf.set_font('DejaVu', size=10)
            pdf.cell(50, 7, f"{label}:", 0, 0, 'L')
            pdf.set_font('DejaVu', size=10)
            pdf.multi_cell(0, 7, str(value), 0, 'L')
            pdf.ln(2) 

    def draw_section_header(title):
        pdf.set_font('DejaVu', size=12)
        pdf.cell(0, 10, title, 0, 1, 'L')
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    draw_section_header("👤 Dados Pessoais")
    draw_field("CPF", membro.get("CPF"))
    draw_field("Data de Nascimento", membro.get("Data de Nascimento"))
    draw_field("Sexo", membro.get("Sexo"))
    draw_field("Estado Civil", membro.get("Estado Civil"))
    draw_field("Profissão", membro.get("Profissão"))
    draw_field("Celular", membro.get("Celular"))
    pdf.ln(5)

    draw_section_header("🏠 Endereço")
    draw_field("CEP", membro.get("CEP"))
    draw_field("Endereço", membro.get("Endereco"))
    draw_field("Bairro", membro.get("Bairro"))
    draw_field("Cidade", membro.get("Cidade"))
    draw_field("UF", membro.get("UF (Endereco)"))
    pdf.ln(5)
    
    draw_section_header("👨‍👩‍👧 Filiação e Origem")
    draw_field("Nome do Pai", membro.get("Nome do Pai"))
    draw_field("Nome da Mãe", membro.get("Nome da Mae"))
    draw_field("Cônjuge", membro.get("Nome do(a) Cônjuge"))
    draw_field("Nacionalidade", membro.get("Nacionalidade"))
    draw_field("Naturalidade", membro.get("Naturalidade"))
    pdf.ln(5)

    draw_section_header("⛪ Dados Eclesiásticos")
    draw_field("Status", membro.get("Status"))
    draw_field("Forma de Admissão", membro.get("Forma de Admissao"))
    draw_field("Data de Admissão", membro.get("Data de Admissao"))
    draw_field("Data de Conversão", membro.get("Data de Conversao"))
    
    return bytes(pdf.output())

# --- Funções de Dados (Google Sheets) ---
NOME_PLANILHA = "Fichario_Membros_PIB_Gaibu"
NOME_ABA = "Membros"

try:
    creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
    creds_dict = json.loads(creds_json_str)
except (KeyError, FileNotFoundError):
    st.error("As credenciais do Google Sheets não foram encontradas.")
    st.stop()

@st.cache_resource(ttl=3600)
def get_client(creds):
    return gspread.service_account_from_dict(creds)

gc = get_client(creds_dict)

HEADERS = [
    "Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao",
    "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)",
    "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge",
    "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)",
    "Grau de Instrução", "Celular", "Data de Conversao", "Data de Admissao",
    "Status", "Observações"
]

def carregar_membros():
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(NOME_PLANILHA)
        ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS))
        ws.insert_row(HEADERS, 1)
        return []
    except gspread.WorksheetNotFound:
        sh = gc.open(NOME_PLANILHA)
        ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS))
        ws.insert_row(HEADERS, 1)
        return []
    records = ws.get_all_records()
    for record in records:
        record['CPF'] = str(record.get('CPF', ''))
        for header in HEADERS:
            if header not in record:
                record[header] = ""
    return records

def salvar_membros(lista):
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear()
        ws.insert_row(HEADERS, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
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
                return {"endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(), "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf_end": data.get("uf", "")}
    except Exception:
        pass
    return None

MAP_KEYS = {"Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao", "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade", "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae", "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade", "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv", "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"}

def limpar_formulario():
    for key in MAP_KEYS.values():
        st.session_state[key] = None if "data" in key else ""
    st.session_state.sexo = "M"

def submeter_formulario():
    # CORREÇÃO DEFINITIVA: Mapeamento explícito para garantir a ordem e corrigir o bug
    novo = {
        "Nome": str(st.session_state.get("nome", "")).strip().upper(),
        "CPF": str(st.session_state.get("cpf", "")).strip().upper(),
        "Sexo": st.session_state.get("sexo", ""),
        "Estado Civil": st.session_state.get("estado_civil", ""),
        "Profissão": str(st.session_state.get("profissao", "")).strip().upper(),
        "Forma de Admissao": st.session_state.get("forma_admissao", ""),
        "Data de Nascimento": st.session_state.data_nasc.strftime('%d/%m/%Y') if st.session_state.data_nasc else "",
        "Nacionalidade": st.session_state.get("nacionalidade", ""),
        "Naturalidade": str(st.session_state.get("naturalidade", "")).strip().upper(),
        "UF (Naturalidade)": st.session_state.get("uf_nat", ""),
        "Nome do Pai": str(st.session_state.get("nome_pai", "")).strip().upper(),
        "Nome da Mae": str(st.session_state.get("nome_mae", "")).strip().upper(),
        "Nome do(a) Cônjuge": str(st.session_state.get("conjuge", "")).strip().upper(),
        "CEP": str(st.session_state.get("cep", "")).strip().upper(),
        "Endereco": str(st.session_state.get("endereco", "")).strip().upper(),
        "Bairro": str(st.session_state.get("bairro", "")).strip().upper(),
        "Cidade": str(st.session_state.get("cidade", "")).strip().upper(),
        "UF (Endereco)": st.session_state.get("uf_end", ""),
        "Grau de Instrução": st.session_state.get("grau_ins", ""),
        "Celular": str(st.session_state.get("celular", "")).strip().upper(),
        "Data de Conversao": st.session_state.data_conv.strftime('%d/%m/%Y') if st.session_state.data_conv else "",
        "Data de Admissao": st.session_state.data_adm.strftime('%d/%m/%Y') if st.session_state.data_adm else "",
        "Status": st.session_state.get("status", ""),
        "Observações": st.session_state.get("observacoes", "").strip()
    }
    
    cpf_digitado = novo.get("CPF")
    is_duplicado = False
    if cpf_digitado: is_duplicado = any(str(m.get("CPF")) == cpf_digitado for m in st.session_state.membros)
    if is_duplicado: st.error("Já existe um membro cadastrado com este CPF.")
    else:
        st.session_state.membros.append(novo)
        salvar_membros(st.session_state.membros)
        st.toast("Membro salvo com sucesso!", icon="🎉")
        limpar_formulario()

def confirmar_mudanca_status():
    chaves_para_atualizar = st.session_state.chaves_para_status
    novo_status_val = st.session_state.novo_status
    obs_adicional = st.session_state.obs_status
    for membro in st.session_state.membros:
        chave_membro = (membro.get('Nome'), membro.get('Data de Nascimento'))
        if chave_membro in chaves_para_atualizar:
            membro['Status'] = novo_status_val
            if obs_adicional and obs_adicional.strip():
                obs_existente = membro.get('Observações', '')
                data_hoje = date.today().strftime("%d/%m/%Y")
                nota_observacao = f"[{data_hoje}] {obs_adicional.strip()}"
                membro['Observações'] = f"{obs_existente}\n{nota_observacao}".strip() if obs_existente else nota_observacao
    salvar_membros(st.session_state.membros)
    st.toast(f"Status de {len(chaves_para_atualizar)} membro(s) alterado com sucesso!", icon="👍")
    st.session_state.confirmando_status, st.session_state.chaves_para_status, st.session_state.obs_status = False, set(), ""

def cancelar_mudanca_status():
    st.session_state.confirmando_status, st.session_state.chaves_para_status, st.session_state.obs_status = False, set(), ""

def init_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""
    if st.session_state.authenticated and "membros" not in st.session_state:
        st.session_state.membros = carregar_membros()
        st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set()
        st.session_state.confirmando_status, st.session_state.chaves_para_status, st.session_state.novo_status, st.session_state.obs_status = False, set(), "", ""
        for key in MAP_KEYS.values():
            if key not in st.session_state: st.session_state[key] = None if "data" in key else ""
        if "sexo" not in st.session_state or not st.session_state.sexo: st.session_state.sexo = "M"

def display_member_details(membro_dict, context_prefix):
    def display_field(label, value):
        if value and str(value).strip():
            st.markdown(f"**{label}:** {value}")
    st.markdown("##### 👤 Dados Pessoais")
    c1, c2 = st.columns(2)
    with c1:
        display_field("CPF", membro_dict.get("CPF"))
        display_field("Sexo", membro_dict.get("Sexo"))
        display_field("Estado Civil", membro_dict.get("Estado Civil"))
    with c2:
        display_field("Data de Nascimento", membro_dict.get("Data de Nascimento"))
        display_field("Celular", membro_dict.get("Celular"))
        display_field("Profissão", membro_dict.get("Profissão"))
    st.divider()
    st.markdown("##### 👨‍👩‍👧 Filiação e Origem")
    c3, c4 = st.columns(2)
    with c3:
        display_field("Nome do Pai", membro_dict.get("Nome do Pai"))
        display_field("Nome da Mãe", membro_dict.get("Nome da Mae"))
    with c4:
        display_field("Nome do(a) Cônjuge", membro_dict.get("Nome do(a) Cônjuge"))
        display_field("Nacionalidade", membro_dict.get("Nacionalidade"))
        display_field("Naturalidade", membro_dict.get("Naturalidade"))
    st.divider()
    st.markdown("##### 🏠 Endereço")
    c5, c6 = st.columns(2)
    with c5:
        display_field("CEP", membro_dict.get("CEP"))
        display_field("Endereço", membro_dict.get("Endereco"))
    with c6:
        display_field("Bairro", membro_dict.get("Bairro"))
        display_field("Cidade", membro_dict.get("Cidade"))
        display_field("UF", membro_dict.get("UF (Endereco)"))
    st.divider()
    st.markdown("##### ⛪ Dados Eclesiásticos")
    c7, c8 = st.columns(2)
    with c7:
        display_field("Status", membro_dict.get("Status"))
        display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))
    with c8:
        display_field("Data de Admissão", membro_dict.get("Data de Admissao"))
        display_field("Data de Conversão", membro_dict.get("Data de Conversao"))
    st.divider()
    st.markdown("##### 📝 Observações")
    obs = membro_dict.get("Observações")
    if obs and obs.strip():
        st.text_area("", value=obs, height=100, disabled=True, label_visibility="collapsed", key=f"obs_{context_prefix}")

# --- C) Lógica Principal de Exibição ---
init_state()

if not st.session_state.get("authenticated", False):
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True)
        st.markdown("---")
        token_response = oauth2.authorize_button("Entrar com Google", key="google_login", redirect_uri=GOOGLE_REDIRECT_URI, scope="openid email profile")
        if token_response:
            try:
                nested_token = token_response.get("token")
                if nested_token:
                    id_token = nested_token.get("id_token")
                    if id_token and isinstance(id_token, str):
                        user_info = jwt.decode(id_token.encode(), options={"verify_signature": False})
                        email = user_info.get("email", "")
                        if email in EMAILS_PERMITIDOS:
                            st.session_state.authenticated, st.session_state.username = True, email
                            st.rerun()
                        else: st.error("Acesso não autorizado para este e-mail.")
                    else: st.error("Resposta de autenticação não continha uma identidade válida.")
                else: st.error("Resposta de autenticação inválida recebida do Google.")
            except Exception as e: st.error(f"Ocorreu um erro ao processar o login: {e}")
else:
    # --- BARRA LATERAL DE AÇÕES ---
    with st.sidebar:
        st.markdown(f"**
