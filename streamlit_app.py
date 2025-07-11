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

st.set_page_config(layout="wide", page_title="Fichário de Membros v4.5")



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

        pdf.cell(col_widths.get(col, 18), line_height, col, border=1, align='C')

    pdf.ln(line_height)

    pdf.set_font_size(7)

    for _, row in df.iterrows():

        for col in cols:

            pdf.cell(col_widths.get(col, 18), line_height, str(row[col]), border=1)

        pdf.ln(line_height)

    return pdf.output(dest='S').encode('latin-1')



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

    for _, row in df.iterrows():

        pdf.cell(130, 10, str(row['Nome Completo']), 1, 0, 'L')

        pdf.cell(60, 10, str(row['Data de Nascimento Completa']), 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')



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

            pdf.multi_cell(0, 7, str(value), 0, 'L')

            pdf.ln(2)

    def draw_section_header(title):

        pdf.set_font('DejaVu', size=12)

        pdf.cell(0, 10, title, 0, 1, 'L')

        pdf.line(10, pdf.get_y(), 200, pdf.get_y())

        pdf.ln(2)

    # Seções

    draw_section_header("👤 Dados Pessoais")

    for label in ["CPF", "Data de Nascimento", "Sexo", "Estado Civil", "Profissão", "Celular"]:

        draw_field(label, membro.get(label))

    pdf.ln(5)

    draw_section_header("🏠 Endereço")

    for label in ["CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)"]:

        draw_field(label, membro.get(label))

    pdf.ln(5)

    draw_section_header("⛪ Dados Eclesiásticos")

    for label in ["Status", "Forma de Admissao", "Data de Admissao", "Data de Conversao"]:

        draw_field(label, membro.get(label))

    return pdf.output(dest='S').encode('latin-1')



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

    "Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento",

    "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge",

    "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)", "Grau de Instrução", "Celular",

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

    records = ws.get_all_records()

    for r in records:

        r['CPF'] = str(r.get('CPF', ''))

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



# --- Estado Inicial ---

def init_state():

    if "authenticated" not in st.session_state:

        st.session_state.authenticated = False

        st.session_state.username = ""

    if st.session_state.authenticated and "membros" not in st.session_state:

        st.session_state.membros = carregar_membros()

        st.session_state.confirmando_exclusao = False

        st.session_state.chaves_para_excluir = set()

        st.session_state.confirmando_status = False

        st.session_state.chaves_para_status = set()

        st.session_state.novo_status = ""

        st.session_state.obs_status = ""



init_state()



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

    st.markdown("##### 🏠 Endereço")

    c3, c4 = st.columns(2)

    with c3:

        display_field("Endereco", membro_dict.get("Endereco"))

        display_field("Bairro", membro_dict.get("Bairro"))

    with c4:

        display_field("Cidade", membro_dict.get("Cidade"))

        display_field("UF", membro_dict.get("UF (Endereco)"))

    st.divider()

    st.markdown("##### ⛪ Dados Eclesiásticos")

    c5, c6 = st.columns(2)

    with c5:

        display_field("Status", membro_dict.get("Status"))

        display_field("Forma de Admissao", membro_dict.get("Forma de Admissao"))

    with c6:

        display_field("Data de Admissao", membro_dict.get("Data de Admissao"))

        display_field("Data de Conversao", membro_dict.get("Data de Conversao"))

    st.divider()

    st.markdown("##### 📝 Observações")

    obs = membro_dict.get("Observações")

    if obs and obs.strip():

        st.text_area("", value=obs, height=100, disabled=True, label_visibility="collapsed", key=f"obs_{context_prefix}")



# --- Interface ---

if not st.session_state.authenticated:

    _, col, _ = st.columns([1, 2, 1])

    with col:

        st.markdown("<h1 align='center'>Fichário de Membros</h1>", unsafe_allow_html=True)

        token_response = oauth2.authorize_button("Entrar com Google", key="google_login", redirect_uri=GOOGLE_REDIRECT_URI, scope="openid email profile")

        if token_response:

            nested = token_response.get("token")

            if nested:

                id_token = nested.get("id_token")

                if id_token:

                    user_info = jwt.decode(id_token, options={"verify_signature": False})

                    email = user_info.get("email", "")

                    if email in EMAILS_PERMITIDOS:

                        st.session_state.authenticated = True

                        st.session_state.username = email

                        st.rerun()

                    else:

                        st.error("Acesso não autorizado.")

                else:

                    st.error("Token inválido.")

            else:

                st.error("Erro no login.")

else:

    col1, col2 = st.columns([4,1])

    with col1:

        st.markdown(f"<p align='right'>Bem-vindo(a), <strong>{st.session_state.username}</strong></p>", unsafe_allow_html=True)

    with col2:

        if st.button("Sair"):

            for k in list(st.session_state.keys()): del st.session_state[k]

            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Lista de Membros", "Busca e Ações", "Aniversariantes", "Ficha Individual"])



    with tab1:

        st.header("Cadastro de Novos Membros")

        with st.form("form_membro"):

            st.subheader("Informações Pessoais")

            c1, c2 = st.columns(2)

            with c1:

                st.text_input("Nome", key="nome")

                st.text_input("CPF", key="cpf")

            with c2:

                st.radio("Sexo", ["M","F"], key="sexo", horizontal=True)

                st.date_input("Data de Nascimento", key="data_nasc", min_value=date(1910,1,1), max_value=date(2030,12,31), format="DD/MM/YYYY")

            st.subheader("Endereço")

            c3, c4 = st.columns(2)

            with c3:

                st.text_input("CEP", key="cep")

            with c4:

                if st.form_submit_button("🔎 Buscar CEP"):

                    digs = re.sub(r"\D","",st.session_state.cep)

                    if len(digs)==8:

                        r = requests.get(f"https://viacep.com.br/ws/{digs}/json/")

                        if r.ok and 'erro' not in r.json():

                            d = r.json()

                            st.session_state.endereco = d.get('logradouro','')

                            st.session_state.bairro = d.get('bairro','')

                            st.session_state.cidade = d.get('localidade','')

                            st.session_state.uf_end = d.get('uf','')

            st.text_input("Endereco", key="endereco")

            st.text_input("Bairro", key="bairro")

            st.text_input("Cidade", key="cidade")

            st.selectbox("UF", ["",*[x for x in os.listdir('fonts')]], key="uf_end")

            st.form_submit_button("💾 Salvar", on_click=lambda: [st.session_state.membros.append({

                "Nome":st.session_state.nome,

                "CPF":st.session_state.cpf,

                "Sexo":st.session_state.sexo,

                "Data de Nascimento":st.session_state.data_nasc.strftime('%d/%m/%Y'),

                "Endereco":st.session_state.endereco,

                "Bairro":st.session_state.bairro,

                "Cidade":st.session_state.cidade,

                "UF (Endereco)":st.session_state.uf_end

            }), salvar_membros(st.session_state.membros)])



    with tab2:

        st.header("Lista de Membros")

        df = pd.DataFrame(st.session_state.membros)

        st.dataframe(df, use_container_width=True)



    with tab3:

        st.header("Buscar e Realizar Ações")

        termo = st.text_input("Buscar por Nome ou CPF", key="busca_termo").strip().upper()

        data_filtro = st.date_input(

            "Buscar por Data de Nascimento",

            value=None,

            key="busca_data",

            format="DD/MM/YYYY"

        )



        df_orig = pd.DataFrame(st.session_state.membros)

        df = df_orig.copy()

        if termo:

            df = df[df.apply(lambda r: termo in r["Nome"].upper() or termo in r["CPF"], axis=1)]

        if data_filtro:

            df = df[df["Data de Nascimento"] == data_filtro.strftime("%d/%m/%Y")]



        if df.empty:

            st.warning("Nenhum encontrado")

        else:

            selecionados = set()

            for i, row in df.iterrows():

                cA, cB = st.columns([1, 9])

                if cA.checkbox("", key=f"ch_{i}"):

                    selecionados.add((row["Nome"], row["Data de Nascimento"]))

                cB.markdown(f"**{row['Nome']}**  CPF: {row['CPF']}")



            d1, d2, d3 = st.columns(3)

            if d1.button("Excluir", disabled=not selecionados):

                st.session_state.chaves_para_excluir = selecionados

                st.session_state.confirmando_exclusao = True



            if d2.button("📄 Exportar Excel", disabled=not selecionados):

                buf = BytesIO()

                pd.DataFrame(

                    [r for r in st.session_state.membros

                     if (r["Nome"], r["Data de Nascimento"]) in selecionados]

                ).to_excel(buf, index=False)

                st.download_button("📄", buf.getvalue(), "selecionados.xlsx")



            if d3.button("📕 Exportar PDF", disabled=not selecionados):

                pdf = criar_pdf_lista(

                    pd.DataFrame(

                        [r for r in st.session_state.membros

                         if (r["Nome"], r["Data de Nascimento"]) in selecionados]

                    )

                )

                st.download_button("📕", pdf, "selecionados.pdf")



            if st.session_state.confirmando_exclusao:

                if st.confirm(

                    f"Confirmar exclusão de {len(selecionados)}?",

                    key="confirm"

                ):

                    novos = [

                        m for m in st.session_state.membros

                        if (m["Nome"], m["Data de Nascimento"]) not in selecionados

                    ]

                    st.session_state.membros = novos

                    salvar_membros(novos)

                    st.success("Registros excluídos")



    with tab4:

        st.header("Aniversariantes")

        mes = st.selectbox(

            "Mês",

            [

                "Janeiro","Fevereiro","Março","Abril","Maio","Junho",

                "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"

            ]

        )

        dfm = pd.DataFrame(st.session_state.membros)

        dfm["data"] = pd.to_datetime(

            dfm["Data de Nascimento"],

            format="%d/%m/%Y",

            errors="coerce"

        )

        dfm = dfm[

            dfm["data"].dt.month ==

            ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",

             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

            .index(mes) + 1

        ]

        if dfm.empty:

            st.info("Nenhum aniversariante neste mês.")

        else:

            dfm["Dia"] = dfm["data"].dt.day

            st.dataframe(dfm[["Dia", "Nome"]], use_container_width=True)

            buf = criar_pdf_aniversariantes(

                dfm[["Nome","Data de Nascimento"]]

                .rename(columns={

                    "Nome": "Nome Completo",

                    "Data de Nascimento": "Data de Nascimento Completa"

                }),

                mes

            )

            st.download_button(

                "📕 Exportar PDF de Aniversariantes",

                buf,

                f"aniversariantes_{mes.lower()}.pdf"

            )



    with tab5:

        st.header("Ficha Individual")

        nomes = [m["Nome"] for m in st.session_state.membros]

        selecionado = st.selectbox("Selecione um membro", [""] + nomes)

        if selecionado:

            membro = next(

                (m for m in st.session_state.membros

                 if m["Nome"] == selecionado),

                None

            )

            if membro:

                display_member_details(membro, "ficha_individual")

                if st.button("📄 Exportar Ficha como PDF"):

                    pdf_data = criar_pdf_ficha(membro)

                    st.download_button(

                        "Clique para Baixar o PDF",

                        pdf_data,

                        f"ficha_{selecionado.replace(' ','_').lower()}.pdf",

                        "application/pdf"

                    )
