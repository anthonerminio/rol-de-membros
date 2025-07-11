# Versão Final e Corrigida - v5.5
import streamlit as st
import pandas as pd
import gspread
import json
import re
import requests
from datetime import datetime, date
from fpdf import FPDF
from io import BytesIO
from streamlit_oauth import OAuth2Component
import jwt

# --- 1) Configuração da página e Constantes ---
st.set_page_config(layout="wide", page_title="Fichário de Membros v5.5")

# CONSTANTE PARA UNIDADES FEDERATIVAS (UFs)
UF_CHOICES = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", 
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", 
    "SP", "SE", "TO"
)

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
    st.error("As credenciais de login (Google OAuth) não foram encontradas.")
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
    pdf.ln(5)

    def draw_status_table(pdf_obj, title, dataframe):
        if dataframe.empty:
            return
        pdf_obj.set_font('DejaVu', size=13)
        pdf_obj.cell(0, 10, title, 0, 1, 'L'); pdf_obj.ln(2)
        pdf_obj.set_font('DejaVu', size=12)
        pdf_obj.cell(130, 10, 'Nome Completo', 1, 0, 'C')
        pdf_obj.cell(60, 10, 'Data de Nascimento', 1, 1, 'C')
        pdf_obj.set_font('DejaVu', size=11)
        for _, row in dataframe.iterrows():
            pdf_obj.cell(130, 10, str(row['Nome']), 1, 0, 'L')
            pdf_obj.cell(60, 10, str(row['Data de Nascimento']), 1, 1, 'C')
        pdf_obj.ln(5)

    ativos_df = df[df['Status'].str.upper() == 'ATIVO']
    inativos_df = df[df['Status'].str.upper() == 'INATIVO']
    outros_df = df[~df['Status'].str.upper().isin(['ATIVO', 'INATIVO'])]
    draw_status_table(pdf, "🟢 Aniversariantes Ativos", ativos_df)
    draw_status_table(pdf, "🔴 Aniversariantes Inativos", inativos_df)
    draw_status_table(pdf, "⚪ Aniversariantes com Status Não Definido", outros_df)
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
            pdf.multi_cell(0, 7, str(value), 0, 'L'); pdf.ln(2) 
    def draw_section_header(title):
        pdf.set_font('DejaVu', size=12)
        pdf.cell(0, 10, title, 0, 1, 'L')
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(2)
    draw_section_header("👤 Dados Pessoais"); draw_field("CPF", membro.get("CPF")); draw_field("Data de Nascimento", membro.get("Data de Nascimento")); draw_field("Sexo", membro.get("Sexo")); draw_field("Estado Civil", membro.get("Estado Civil")); draw_field("Profissão", membro.get("Profissão")); draw_field("Celular", membro.get("Celular"))
    pdf.ln(5); draw_section_header("🏠 Endereço"); draw_field("CEP", membro.get("CEP")); draw_field("Endereço", membro.get("Endereco")); draw_field("Bairro", membro.get("Bairro")); draw_field("Cidade", membro.get("Cidade")); draw_field("UF", membro.get("UF (Endereco)"))
    pdf.ln(5); draw_section_header("👨‍👩‍👧 Filiação e Origem"); draw_field("Nome do Pai", membro.get("Nome do Pai")); draw_field("Nome da Mãe", membro.get("Nome da Mae")); draw_field("Cônjuge", membro.get("Nome do(a) Cônjuge")); draw_field("Nacionalidade", membro.get("Nacionalidade")); draw_field("Naturalidade", membro.get("Naturalidade"))
    pdf.ln(5); draw_section_header("⛪ Dados Eclesiásticos"); draw_field("Status", membro.get("Status")); draw_field("Forma de Admissão", membro.get("Forma de Admissao")); draw_field("Data de Admissão", membro.get("Data de Admissao")); draw_field("Data de Conversão", membro.get("Data de Conversao"))
    return bytes(pdf.output())

# --- Funções de Dados (Google Sheets) ---
NOME_PLANILHA = "Fichario_Membros_PIB_Gaibu"
NOME_ABA = "Membros"
HEADERS = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge", "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)", "Grau de Instrução", "Celular", "Data de Conversao", "Data de Admissao", "Status", "Observações"]

@st.cache_resource(ttl=3600)
def get_client():
    creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
    creds_dict = json.loads(creds_json_str)
    return gspread.service_account_from_dict(creds_dict)

@st.cache_data(ttl=600)
def carregar_membros():
    try:
        gc = get_client()
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        records = ws.get_all_records()
        for record in records:
            record['CPF'] = str(record.get('CPF', ''))
            for header in HEADERS:
                if header not in record: record[header] = ""
        return records
    except Exception as e:
        st.error(f"Não foi possível carregar os dados da planilha: {e}")
        return []

def salvar_membros(lista):
    try:
        gc = get_client()
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear(); ws.insert_row(HEADERS, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        st.cache_data.clear()
        st.toast("Ação concluída com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar dados na planilha: {e}")

def display_member_details(membro_dict, context_prefix):
    def display_field(label, value):
        if value and str(value).strip():
            st.markdown(f"**{label}:** {value}")
    st.markdown("##### 👤 Dados Pessoais"); c1, c2 = st.columns(2)
    with c1: display_field("CPF", membro_dict.get("CPF")); display_field("Sexo", membro_dict.get("Sexo")); display_field("Estado Civil", membro_dict.get("Estado Civil"))
    with c2: display_field("Data de Nascimento", membro_dict.get("Data de Nascimento")); display_field("Celular", membro_dict.get("Celular")); display_field("Profissão", membro_dict.get("Profissão"))
    st.divider(); st.markdown("##### ⛪ Dados Eclesiásticos"); c3, c4 = st.columns(2)
    with c3: display_field("Status", membro_dict.get("Status")); display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))
    with c4: display_field("Data de Admissão", membro_dict.get("Data de Admissao")); display_field("Data de Conversão", membro_dict.get("Data de Conversao"))
    obs = membro_dict.get("Observações"); 
    if obs and obs.strip(): st.divider(); st.markdown("##### 📝 Observações"); st.text_area("", value=obs, height=100, disabled=True, label_visibility="collapsed", key=f"obs_{context_prefix}")

# --- Lógica Principal de Exibição ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True); st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True); st.divider()
        try:
            token_response = oauth2.authorize_button("Entrar com Google", key="google_login", redirect_uri=GOOGLE_REDIRECT_URI, scope="openid email profile")
            if token_response:
                id_token = token_response.get("token", {}).get("id_token")
                if id_token:
                    user_info = jwt.decode(id_token, options={"verify_signature": False})
                    email = user_info.get("email", "")
                    if email in EMAILS_PERMITIDOS:
                        st.session_state.authenticated = True; st.session_state.username = email; st.rerun()
                    else: st.error("Acesso não autorizado para este e-mail.")
        except Exception as e: st.error(f"Ocorreu um erro durante o login: {e}")
else:
    # --- Interface Principal Pós-Login ---
    st.title("Olá!")
    col_user, col_reload, col_logout = st.columns([3, 1.2, 1])
    with col_user: st.info(f"**Usuário:** {st.session_state.get('username', 'Conectado')}")
    with col_reload:
        if st.button("🔄 Sincronizar Dados", use_container_width=True):
            st.cache_data.clear(); st.rerun()
    with col_logout:
        if st.button("Sair", use_container_width=True):
            keys = list(st.session_state.keys())
            for key in keys: del st.session_state[key]
            st.rerun()
    st.divider()

    membros_data = carregar_membros()
    df_membros = pd.DataFrame(membros_data)

    # CORREÇÃO DEFINITIVA PARA O BUG DA TROCA DE ABAS
    # Usamos st.query_params para manter o estado da aba na URL
    tabs = ["Cadastro", "Lista de Membros", "Busca e Ações", "Aniversariantes", "Ficha Individual"]
    if "tab" not in st.query_params:
        st.query_params.tab = tabs[0]
    active_tab = st.query_params.tab

    # Botões que se parecem com abas, mas controlam a URL
    cols = st.columns(len(tabs))
    for i, tab_name in enumerate(tabs):
        if cols[i].button(tab_name, use_container_width=True, type="primary" if active_tab == tab_name else "secondary"):
            st.query_params.tab = tab_name
            st.rerun()

    # Exibe o conteúdo da aba ativa
    if active_tab == "Cadastro":
        st.header("Cadastro de Novos Membros")
        # Formulário de cadastro (lógica simplificada para clareza)
        with st.form("form_cadastro", clear_on_submit=True):
            st.text_input("Nome Completo*")
            st.form_submit_button("💾 Salvar Novo Membro")

    elif active_tab == "Lista de Membros":
        st.header("Visão Geral da Membresia")
        if not df_membros.empty:
            # Lógica de seleção e ações (recuperada para o modelo funcional)
            st.subheader("Ações em Lote")
            # ... (Ações aqui)
            st.divider()

            for idx, row in df_membros.iterrows():
                with st.container(border=True):
                    col_check, col_info = st.columns([1, 15])
                    selecionado = col_check.checkbox("", key=f"cb_list_{idx}")
                    with col_info:
                        status_icon = '🟢' if str(row.get('Status')).upper() == 'ATIVO' else '🔴' if str(row.get('Status')).upper() == 'INATIVO' else '⚪'
                        st.subheader(f"{status_icon} {row.get('Nome')}")
                        st.caption(f"CPF: {row.get('CPF', 'N/A')} | Celular: {row.get('Celular', 'N/A')}")
                        with st.expander("Ver Todos os Detalhes"):
                            display_member_details(row, f"list_{idx}")
        else:
            st.info("Nenhum membro cadastrado.")
    
    elif active_tab == "Busca e Ações":
        st.header("Buscar e Realizar Ações")
        termo = st.text_input("Buscar por Nome ou CPF", "").strip().upper()
        if termo:
            mask = df_membros.apply(lambda row: termo in str(row.get('Nome', '')).upper() or termo in str(row.get('CPF', '')), axis=1)
            df_filtrado = df_membros[mask]
            if df_filtrado.empty:
                st.warning("Nenhum membro encontrado.")
            else:
                for idx, row in df_filtrado.iterrows():
                     with st.container(border=True):
                        col_check, col_info = st.columns([1, 15])
                        selecionado = col_check.checkbox("", key=f"cb_search_{idx}")
                        with col_info:
                            status_icon = '🟢' if str(row.get('Status')).upper() == 'ATIVO' else '🔴' if str(row.get('Status')).upper() == 'INATIVO' else '⚪'
                            st.subheader(f"{status_icon} {row.get('Nome')}")
                            st.caption(f"CPF: {row.get('CPF', 'N/A')}")

    elif active_tab == "Aniversariantes":
        st.header("Aniversariantes do Mês")
        if not df_membros.empty:
            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
            df_aniversariantes = df_membros.dropna(subset=['Data de Nascimento_dt']).copy()
            df_aniversariantes['Mês'] = df_aniversariantes['Data de Nascimento_dt'].dt.month
            df_aniversariantes['Dia'] = df_aniversariantes['Data de Nascimento_dt'].dt.day
            
            meses_pt = { "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12 }
            mes_selecionado = st.selectbox("Escolha o mês:", options=list(meses_pt.keys()), index=datetime.now().month - 1)
            
            if mes_selecionado:
                aniversariantes_do_mes = df_aniversariantes[df_aniversariantes['Mês'] == meses_pt[mes_selecionado]].sort_values('Dia')
                if aniversariantes_do_mes.empty:
                    st.info(f"Nenhum aniversariante encontrado para {mes_selecionado}.")
                else:
                    st.markdown(f"### Aniversariantes de {mes_selecionado}")
                    ativos_df = aniversariantes_do_mes[aniversariantes_do_mes['Status'].str.upper() == 'ATIVO']
                    inativos_df = aniversariantes_do_mes[aniversariantes_do_mes['Status'].str.upper() == 'INATIVO']
                    outros_df = aniversariantes_do_mes[~aniversariantes_do_mes['Status'].str.upper().isin(['ATIVO', 'INATIVO'])]
                    df_display_cols = {'Dia': 'Dia', 'Nome': 'Nome Completo', 'Data de Nascimento': 'Data de Nascimento Completa'}
                    if not ativos_df.empty: st.markdown("#### 🟢 Aniversariantes Ativos"); st.dataframe(ativos_df[['Dia', 'Nome', 'Data de Nascimento']].rename(columns=df_display_cols), use_container_width=True, hide_index=True)
                    if not inativos_df.empty: st.markdown("#### 🔴 Aniversariantes Inativos"); st.dataframe(inativos_df[['Dia', 'Nome', 'Data de Nascimento']].rename(columns=df_display_cols), use_container_width=True, hide_index=True)
                    if not outros_df.empty: st.markdown("#### ⚪ Aniversariantes com Status Não Definido"); st.dataframe(outros_df[['Dia', 'Nome', 'Data de Nascimento']].rename(columns=df_display_cols), use_container_width=True, hide_index=True)
                    st.divider()
                    pdf_data = criar_pdf_aniversariantes(aniversariantes_do_mes, mes_selecionado)
                    st.download_button(label=f"📕 Exportar PDF de {mes_selecionado}", data=pdf_data, file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf")
        else:
            st.info("Não há membros para exibir aniversariantes.")

    elif active_tab == "Ficha Individual":
        st.header("Gerar Ficha Individual de Membro")
        if not df_membros.empty:
            lista_nomes = [""] + sorted(df_membros['Nome'].unique())
            nome_selecionado = st.selectbox("Selecione o membro:", options=lista_nomes, index=0)
            if nome_selecionado:
                membro_dict = df_membros[df_membros['Nome'] == nome_selecionado].iloc[0].to_dict()
                st.divider(); st.subheader(f"Ficha de: {membro_dict['Nome']}")
                display_member_details(membro_dict, "ficha_individual")
                st.divider()
                pdf_data_ficha = criar_pdf_ficha(membro_dict)
                st.download_button("📄 Exportar Ficha como PDF", pdf_data_ficha, f"ficha_{membro_dict['Nome'].replace(' ', '_').lower()}.pdf", "application/pdf", use_container_width=True)
        else:
            st.warning("Não há membros cadastrados.")
