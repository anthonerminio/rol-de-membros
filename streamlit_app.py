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
    EMAILS_PERMITIDOS = {"antonio.esn01@gmail.com", "neto1999.legal@gmail.com", "adrielsoliveira1907@gmail.com"}

    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token"
    )
except (KeyError, FileNotFoundError):
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

def criar_pdf_aniversariantes(df, mes_nome):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, f'Aniversariantes de {mes_nome}', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(130, 10, 'Nome Completo', 1, 0, 'C')
    pdf.cell(60, 10, 'Data de Nascimento', 1, 1, 'C')
    
    pdf.set_font('helvetica', '', 11)
    for index, row in df.iterrows():
        nome = str(row['Nome']).encode('latin-1', 'replace').decode('latin-1')
        data_nasc = str(row['Data de Nascimento']).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(130, 10, nome, 1, 0, 'L')
        pdf.cell(60, 10, data_nasc, 1, 1, 'C')
        
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
    return ws.get_all_records()

def salvar_membros(lista):
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear()
        ws.insert_row(HEADERS, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]
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
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""

    if st.session_state.authenticated and "membros" not in st.session_state:
        st.session_state.membros = carregar_membros()
        st.session_state.confirmando_exclusao = False
        st.session_state.cpfs_para_excluir = set()
        form_keys = ["nome", "cpf", "sexo", "estado_civil", "profissao", "forma_admissao", "data_nasc", "nacionalidade", "naturalidade", "uf_nat", "nome_pai", "nome_mae", "conjuge", "cep", "endereco", "bairro", "cidade", "uf_end", "grau_ins", "celular", "data_conv", "data_adm", "status", "observacoes"]
        for key in form_keys:
            if key not in st.session_state:
                st.session_state[key] = None if "data" in key else ""
        if "sexo" not in st.session_state or not st.session_state.sexo:
            st.session_state.sexo = "M"

# --- C) Lógica Principal de Exibição ---
init_state()

if not st.session_state.get("authenticated", False):
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True)
        st.markdown("---")
        token_response = oauth2.authorize_button(
            "Entrar com Google",
            key="google_login",
            redirect_uri=GOOGLE_REDIRECT_URI,
            scope="openid email profile"
        )
        if token_response:
            try:
                nested_token = token_response.get("token")
                if nested_token:
                    id_token = nested_token.get("id_token")
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
                        st.error("Resposta de autenticação não continha uma identidade válida.")
                else:
                    st.error("Resposta de autenticação inválida recebida do Google.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o login: {e}")
else:
    _, col_content = st.columns([1, 1])
    with col_content:
        col_bem_vindo, col_logout = st.columns([3, 1])
        with col_bem_vindo:
            st.markdown(f"<p style='text-align: right; padding-top: 8px;'>Bem-vindo(a), <strong>{st.session_state.get('username', '')}</strong>!</p>", unsafe_allow_html=True)
        with col_logout:
            if st.button("Sair"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
    st.markdown("---")
    
    # Adicionada a 4ª aba
    tab1, tab2, tab3, tab4 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir", "Aniversariantes do Mês"])

    with tab1:
        # Código da aba 1 (inalterado)
        st.header("Cadastro de Novos Membros")
        # ...

    with tab2:
        # Código da aba 2 (inalterado)
        st.header("Lista de Membros")
        # ...

    with tab3:
        # Código da aba 3 (inalterado)
        st.header("Buscar, Exportar e Excluir Membros")
        # ...

    # --- NOVA ABA: ANIVERSARIANTES ---
    with tab4:
        st.header("Aniversariantes do Mês")

        df_membros = pd.DataFrame(st.session_state.membros)

        if df_membros.empty:
            st.warning("Não há membros cadastrados para exibir.")
        else:
            # Prepara os dados de data de nascimento
            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
            df_membros.dropna(subset=['Data de Nascimento_dt'], inplace=True) # Remove linhas sem data válida
            df_membros['Mês'] = df_membros['Data de Nascimento_dt'].dt.month
            df_membros['Dia'] = df_membros['Data de Nascimento_dt'].dt.day

            meses_pt = {
                "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,
                "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
            }

            mes_selecionado = st.selectbox(
                "Escolha o mês para ver a lista de aniversariantes:",
                options=list(meses_pt.keys()),
                index=None,
                placeholder="Selecione um mês..."
            )

            if mes_selecionado:
                num_mes = meses_pt[mes_selecionado]
                aniversariantes_df = df_membros[df_membros['Mês'] == num_mes].sort_values('Dia')

                st.markdown(f"### Aniversariantes de {mes_selecionado}")

                if aniversariantes_df.empty:
                    st.info("Nenhum aniversariante encontrado para este mês.")
                else:
                    # Prepara o dataframe para exibição
                    df_display = aniversariantes_df[['Dia', 'Nome', 'Data de Nascimento']].copy()
                    df_display.rename(columns={'Dia': 'Dia', 'Nome': 'Nome Completo', 'Data de Nascimento': 'Data de Nascimento Completa'}, inplace=True)
                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    
                    # Lógica de exportação para PDF
                    pdf_data = criar_pdf_aniversariantes(df_display, mes_selecionado)
                    st.download_button(
                        label=f"📕 Exportar PDF de {mes_selecionado}",
                        data=pdf_data,
                        file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf",
                        mime="application/pdf"
                    )
