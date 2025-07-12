# Fichario de Membros PIB Gaibu - v7.2

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

st.set_page_config(layout="wide", page_title="Fichário de Membros v7.2")



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



def criar_pdf_exportacao_busca(df):

    pdf = FPDF(orientation='P', unit='mm', format='A4')

    pdf.add_page()

    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)

    

    pdf.set_font("DejaVu", size=16)

    pdf.cell(0, 10, "Relatório de Membros Selecionados", 0, 1, 'C')

    pdf.ln(10)



    for _, row in df.iterrows():

        pdf.set_font("DejaVu", size=12)

        pdf.cell(0, 8, str(row["Nome"]), 0, 1, 'L')

        

        pdf.set_font("DejaVu", size=10)

        pdf.cell(0, 6, f"  - Data de Nascimento: {row['Data de Nascimento']}", 0, 1, 'L')

        pdf.cell(0, 6, f"  - Telefone: {row['Celular']}", 0, 1, 'L')

        pdf.cell(0, 6, f"  - Forma de Admissão: {row['Forma de Admissao']}", 0, 1, 'L')

        pdf.cell(0, 6, f"  - Data de Admissão: {row['Data de Admissao']}", 0, 1, 'L')

        pdf.cell(0, 6, f"  - Data de Conversão: {row['Data de Conversao']}", 0, 1, 'L')

        

        pdf.ln(5)

        pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())

        pdf.ln(5)

        

    return bytes(pdf.output())



def criar_pdf_aniversariantes_com_status(ativos_df, inativos_df, outros_df, mes_nome):

    pdf = FPDF(orientation='P', unit='mm', format='A4')

    pdf.add_page()

    try:

        pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)

    except RuntimeError:

        pdf.set_font("Arial", size=16)



    pdf.set_font("DejaVu", size=16)

    pdf.cell(0, 10, f'Aniversariantes de {mes_nome}', 0, 1, 'C')

    pdf.ln(10)



    def draw_section(title, df_section):

        if not df_section.empty:

            pdf.set_font('DejaVu', '', size=14)

            pdf.cell(0, 10, title, 0, 1, 'L')

            pdf.ln(2)

            

            pdf.set_font('DejaVu', '', size=11)

            for _, row in df_section.iterrows():

                nome_completo = str(row.get('Nome Completo', ''))

                data_nasc = str(row.get('Data de Nascimento Completa', ''))

                dia = data_nasc.split('/')[0] if '/' in data_nasc else data_nasc

                pdf.cell(0, 8, f"Dia {dia}  -  {nome_completo}", 0, 1, 'L')

            pdf.ln(8)



    draw_section("🟢 Aniversariantes Ativos", ativos_df)

    draw_section("🔴 Aniversariantes Inativos", inativos_df)

    draw_section("⚪ Aniversariantes com Status Não Definido", outros_df)



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

            pdf.set_font('DejaVu', '', size=10)

            pdf.cell(50, 7, f"{label}:", 0, 0, 'L')

            pdf.set_font('DejaVu', '', size=10)

            pdf.multi_cell(0, 7, str(value), 0, 'L')

            pdf.ln(2)



    def draw_section_header(title):

        pdf.set_font('DejaVu', '', size=12)

        pdf.cell(0, 10, title, 0, 1, 'L')

        pdf.line(10, pdf.get_y(), 200, pdf.get_y())

        pdf.ln(4)



    draw_section_header("👤 Dados Pessoais")

    draw_field("CPF", membro.get("CPF")); draw_field("Data de Nascimento", membro.get("Data de Nascimento")); draw_field("Sexo", membro.get("Sexo")); draw_field("Estado Civil", membro.get("Estado Civil")); draw_field("Profissão", membro.get("Profissão")); draw_field("Celular", membro.get("Celular"))

    pdf.ln(5)

    

    draw_section_header("🏠 Endereço")

    draw_field("CEP", membro.get("CEP")); draw_field("Endereço", membro.get("Endereco")); draw_field("Bairro", membro.get("Bairro")); draw_field("Cidade", membro.get("Cidade")); draw_field("UF", membro.get("UF (Endereco)"))

    pdf.ln(5)



    draw_section_header("👨‍👩‍👧 Filiação e Origem")

    draw_field("Nome do Pai", membro.get("Nome do Pai")); draw_field("Nome da Mãe", membro.get("Nome da Mae")); draw_field("Cônjuge", membro.get("Nome do(a) Cônjuge")); draw_field("Nacionalidade", membro.get("Nacionalidade")); draw_field("Naturalidade", membro.get("Naturalidade"))

    pdf.ln(5)



    draw_section_header("⛪ Dados Eclesiásticos")

    draw_field("Status", membro.get("Status")); draw_field("Forma de Admissão", membro.get("Forma de Admissao")); draw_field("Data de Admissão", membro.get("Data de Admissao")); draw_field("Data de Conversão", membro.get("Data de Conversao"))

    pdf.ln(5)

    

    if membro.get("Observações") and str(membro.get("Observações")).strip():

        draw_section_header("📝 Observações")

        draw_field("", membro.get("Observações"))



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

HEADERS = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge", "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)", "Grau de Instrução", "Celular", "Data de Conversao", "Data de Admissao", "Status", "Observações"]



def carregar_membros():

    try:

        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)

    except gspread.SpreadsheetNotFound:

        sh = gc.create(NOME_PLANILHA); ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS)); ws.insert_row(HEADERS, 1)

        return []

    except gspread.WorksheetNotFound:

        sh = gc.open(NOME_PLANILHA); ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS)); ws.insert_row(HEADERS, 1)

        return []

    records = ws.get_all_records()

    for record in records:

        record['CPF'] = str(record.get('CPF', ''))

        for header in HEADERS:

            if header not in record: record[header] = ""

    return records



def salvar_membros(lista):

    try:

        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)

        ws.clear(); ws.insert_row(HEADERS, 1)

        if lista:

            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]

            ws.append_rows(rows, value_input_option="USER_ENTERED")

    except Exception as e:

        st.error(f"Erro ao salvar: {e}")



def buscar_cep(cep):

    cep = re.sub(r"[^\d]", "", cep)

    if len(cep) != 8: return None

    try:

        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/")

        if resp.status_code == 200:

            data = resp.json()

            if "erro" not in data:

                return {"endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(), "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf_end": data.get("uf", "")}

    except Exception: pass

    return None



MAP_KEYS = {"Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao", "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade", "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae", "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade", "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv", "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"}



def limpar_formulario():

    for key in MAP_KEYS.values():

        st.session_state[key] = None if "data" in key else ""

    st.session_state.sexo = "M"



def submeter_formulario():

    novo = {"Nome": str(st.session_state.get("nome", "")).strip().upper(), "CPF": str(st.session_state.get("cpf", "")).strip().upper(), "Sexo": st.session_state.get("sexo", ""), "Estado Civil": st.session_state.get("estado_civil", ""), "Profissão": str(st.session_state.get("profissao", "")).strip().upper(), "Forma de Admissao": st.session_state.get("forma_admissao", ""), "Data de Nascimento": st.session_state.data_nasc.strftime('%d/%m/%Y') if st.session_state.data_nasc else "", "Nacionalidade": st.session_state.get("nacionalidade", ""), "Naturalidade": str(st.session_state.get("naturalidade", "")).strip().upper(), "UF (Naturalidade)": st.session_state.get("uf_nat", ""), "Nome do Pai": str(st.session_state.get("nome_pai", "")).strip().upper(), "Nome da Mae": str(st.session_state.get("nome_mae", "")).strip().upper(), "Nome do(a) Cônjuge": str(st.session_state.get("conjuge", "")).strip().upper(), "CEP": str(st.session_state.get("cep", "")).strip().upper(), "Endereco": str(st.session_state.get("endereco", "")).strip().upper(), "Bairro": str(st.session_state.get("bairro", "")).strip().upper(), "Cidade": str(st.session_state.get("cidade", "")).strip().upper(), "UF (Endereco)": st.session_state.get("uf_end", ""), "Grau de Instrução": st.session_state.get("grau_ins", ""), "Celular": str(st.session_state.get("celular", "")).strip().upper(), "Data de Conversao": st.session_state.data_conv.strftime('%d/%m/%Y') if st.session_state.data_conv else "", "Data de Admissao": st.session_state.data_adm.strftime('%d/%m/%Y') if st.session_state.data_adm else "", "Status": st.session_state.get("status", ""), "Observações": st.session_state.get("observacoes", "").strip()}

    cpf_digitado = novo.get("CPF")

    is_duplicado = False

    if cpf_digitado: is_duplicado = any(str(m.get("CPF")) == cpf_digitado for m in st.session_state.membros)

    if is_duplicado: st.error("Já existe um membro cadastrado com este CPF.")

    else:

        st.session_state.membros.append(novo)

        salvar_membros(st.session_state.membros)

        st.toast("Membro salvo com sucesso!", icon="🎉")

        limpar_formulario()



def submeter_edicao_formulario():

    index = st.session_state.editing_member_index

    membro_editado = st.session_state.membros[index].copy()



    membro_editado.update({

        "Nome": str(st.session_state.get("edit_nome", "")).strip().upper(),

        "CPF": str(st.session_state.get("edit_cpf", "")).strip(),

        "Sexo": st.session_state.get("edit_sexo", ""),

        "Estado Civil": st.session_state.get("edit_estado_civil", ""),

        "Profissão": str(st.session_state.get("edit_profissao", "")).strip().upper(),

        "Forma de Admissao": st.session_state.get("edit_forma_admissao", ""),

        "Data de Nascimento": st.session_state.edit_data_nasc.strftime('%d/%m/%Y') if st.session_state.edit_data_nasc else "",

        "Nacionalidade": st.session_state.get("edit_nacionalidade", ""),

        "Naturalidade": str(st.session_state.get("edit_naturalidade", "")).strip().upper(),

        "UF (Naturalidade)": st.session_state.get("edit_uf_nat", ""),

        "Nome do Pai": str(st.session_state.get("edit_nome_pai", "")).strip().upper(),

        "Nome da Mae": str(st.session_state.get("edit_nome_mae", "")).strip().upper(),

        "Nome do(a) Cônjuge": str(st.session_state.get("edit_conjuge", "")).strip().upper(),

        "CEP": str(st.session_state.get("edit_cep", "")).strip(),

        "Endereco": str(st.session_state.get("edit_endereco", "")).strip().upper(),

        "Bairro": str(st.session_state.get("edit_bairro", "")).strip().upper(),

        "Cidade": str(st.session_state.get("edit_cidade", "")).strip().upper(),

        "UF (Endereco)": st.session_state.get("edit_uf_end", ""),

        "Grau de Instrução": st.session_state.get("edit_grau_ins", ""),

        "Celular": str(st.session_state.get("edit_celular", "")).strip(),

        "Data de Conversao": st.session_state.edit_data_conv.strftime('%d/%m/%Y') if st.session_state.edit_data_conv else "",

        "Data de Admissao": st.session_state.edit_data_adm.strftime('%d/%m/%Y') if st.session_state.edit_data_adm else "",

        "Status": st.session_state.get("edit_status", ""),

        "Observações": st.session_state.get("edit_observacoes", "").strip()

    })



    st.session_state.membros[index] = membro_editado

    salvar_membros(st.session_state.membros)

    st.toast("Dados salvos com sucesso!", icon="👍")

    st.session_state.editing_member_key = None 



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

    for key in st.session_state.keys():

        if key.startswith("select_list_"):

            st.session_state[key] = False



def cancelar_mudanca_status():

    st.session_state.confirmando_status, st.session_state.chaves_para_status, st.session_state.obs_status = False, set(), ""



def init_state():

    if "authenticated" not in st.session_state:

        st.session_state.authenticated = False

        st.session_state.username = ""

    if st.session_state.authenticated:

        if "membros" not in st.session_state:

            st.session_state.membros = carregar_membros()

        

        if "confirmando_exclusao" not in st.session_state:

             st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set()

        if "confirmando_status" not in st.session_state:

             st.session_state.confirmando_status, st.session_state.chaves_para_status, st.session_state.novo_status, st.session_state.obs_status = False, set(), "", ""

        if "selecao_lista" not in st.session_state:

            st.session_state.selecao_lista = set()

        if "selecao_busca" not in st.session_state:

            st.session_state.selecao_busca = set()

        

        if "editing_member_key" not in st.session_state:

            st.session_state.editing_member_key = None

        if "editing_member_index" not in st.session_state:

            st.session_state.editing_member_index = None



        for key in MAP_KEYS.values():

            if key not in st.session_state: st.session_state[key] = None if "data" in key else ""

        if "sexo" not in st.session_state or not st.session_state.sexo: st.session_state.sexo = "M"



# <<< CORREÇÃO AQUI: A função display_member_details foi adicionada novamente.

def display_member_details(membro_dict, context_prefix):

    """Função para exibir os detalhes de um membro em colunas."""

    def display_field(label, value):

        if value and str(value).strip(): st.markdown(f"**{label}:** {value}")

    st.markdown("##### 👤 Dados Pessoais")

    c1, c2 = st.columns(2)

    with c1:

        display_field("CPF", membro_dict.get("CPF")); display_field("Sexo", membro_dict.get("Sexo")); display_field("Estado Civil", membro_dict.get("Estado Civil"))

    with c2:

        display_field("Data de Nascimento", membro_dict.get("Data de Nascimento")); display_field("Celular", membro_dict.get("Celular")); display_field("Profissão", membro_dict.get("Profissão"))

    st.divider()

    st.markdown("##### 👨‍👩‍👧 Filiação e Origem")

    c3, c4 = st.columns(2)

    with c3:

        display_field("Nome do Pai", membro_dict.get("Nome do Pai")); display_field("Nome da Mãe", membro_dict.get("Nome da Mae"))

    with c4:

        display_field("Nome do(a) Cônjuge", membro_dict.get("Nome do(a) Cônjuge")); display_field("Nacionalidade", membro_dict.get("Nacionalidade")); display_field("Naturalidade", membro_dict.get("Naturalidade"))

    st.divider()

    st.markdown("##### 🏠 Endereço")

    c5, c6 = st.columns(2)

    with c5:

        display_field("CEP", membro_dict.get("CEP")); display_field("Endereço", membro_dict.get("Endereco"))

    with c6:

        display_field("Bairro", membro_dict.get("Bairro")); display_field("Cidade", membro_dict.get("Cidade")); display_field("UF", membro_dict.get("UF (Endereco)"))

    st.divider()

    st.markdown("##### ⛪ Dados Eclesiásticos")

    c7, c8 = st.columns(2)

    with c7:

        display_field("Status", membro_dict.get("Status")); display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))

    with c8:

        display_field("Data de Admissão", membro_dict.get("Data de Admissao")); display_field("Data de Conversão", membro_dict.get("Data de Conversao"))

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

        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True); st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True); st.markdown("---")

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

                            st.session_state.authenticated, st.session_state.username = True, email; st.rerun()

                        else: st.error("Acesso não autorizado para este e-mail.")

                    else: st.error("Resposta de autenticação não continha uma identidade válida.")

                else: st.error("Resposta de autenticação inválida recebida do Google.")

            except Exception as e: st.error(f"Ocorreu um erro ao processar o login: {e}")

else:

    st.title("Olá!")

    col_user, col_reload, col_logout = st.columns([3, 1.2, 1])

    with col_user:

        st.info(f"**Usuário:** {st.session_state.get('username', '')}")

    with col_reload:

        if st.button("🔄 Sincronizar Dados", use_container_width=True):

            st.session_state.membros = carregar_membros()

            st.toast("Dados sincronizados com sucesso!")

            st.rerun()

    with col_logout:

        if st.button("Sair", use_container_width=True):

            for key in list(st.session_state.keys()): del st.session_state[key]

            st.rerun()

    st.divider()



    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Lista de Membros", "Busca e Ações", "Aniversariantes", "✏️ Fichas de Membros"])



    with tab1:

        st.header("Cadastro de Novos Membros")

        with st.form("form_membro"):

            st.subheader("Informações Pessoais"); c1, c2 = st.columns(2)

            with c1:

                st.text_input("Nome", key="nome"); st.text_input("CPF", key="cpf"); st.selectbox("Estado Civil", ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"], key="estado_civil"); st.selectbox("Forma de Admissao", ["", "Batismo", "Transferência", "Aclamação"], key="forma_admissao")

            with c2:

                st.radio("Sexo", ["M", "F"], key="sexo", horizontal=True); st.date_input("Data de Nascimento", key="data_nasc", value=None, min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY"); st.text_input("Profissão", key="profissao"); st.text_input("Celular", key="celular")

            st.subheader("Filiação e Origem"); c3, c4 = st.columns(2)

            with c3:

                st.text_input("Nome do Pai", key="nome_pai"); st.text_input("Nome da Mãe", key="nome_mae"); st.text_input("Nome do(a) Cônjuge", key="conjuge")

            with c4:

                st.selectbox("Nacionalidade", ["", "Brasileiro(a)", "Estrangeiro(a)"], key="nacionalidade"); st.text_input("Naturalidade", key="naturalidade"); st.selectbox("UF (Naturalidade)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_nat")

            st.subheader("Endereço"); col_cep, col_btn_cep, col_spacer = st.columns([1,1,2])

            with col_cep: st.text_input("CEP", key="cep")

            with col_btn_cep:

                if st.form_submit_button("🔎 Buscar CEP"):

                    dados_cep = buscar_cep(st.session_state.cep)

                    if dados_cep:

                        st.session_state.update(dados_cep)

                        st.toast("Endereço preenchido!", icon="🏠")

                    elif st.session_state.cep: st.warning("CEP não encontrado ou inválido.")

            c7, c8, c9, c10 = st.columns(4)

            with c7: st.text_input("Endereco", key="endereco")

            with c8: st.text_input("Bairro", key="bairro")

            with c9: st.text_input("Cidade", key="cidade")

            with c10: st.selectbox("UF (Endereco)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_end")

            st.subheader("Informações Adicionais"); c11, c12, c13 = st.columns(3)

            with c11:

                st.selectbox("Grau de Instrução", ["", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo", "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"], key="grau_ins"); st.selectbox("Status", ["Ativo", "Inativo"], key="status")

            with c12:

                st.date_input("Data de Conversao", key="data_conv", value=None, min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY"); st.date_input("Data de Admissao", key="data_adm", value=None, min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")

            with c13: st.text_area("Observações", key="observacoes")

            st.markdown("---"); st.form_submit_button("💾 Salvar Membro", on_click=submeter_formulario)



    with tab2:

        st.header("Visão Geral da Membresia")

        if "membros" in st.session_state and st.session_state.membros:

            df_membros_tab2 = pd.DataFrame(st.session_state.membros)

            total_membros = len(df_membros_tab2); ativos = len(df_membros_tab2[df_membros_tab2['Status'].str.upper() == 'ATIVO']); inativos = len(df_membros_tab2[df_membros_tab2['Status'].str.upper() == 'INATIVO']); sem_status = total_membros - ativos - inativos

            col1_metric, col2_metric, col3_metric, col4_metric = st.columns(4)

            col1_metric.metric("Total de Membros", f"{total_membros} 👥"); col2_metric.metric("Membros Ativos", f"{ativos} 🟢"); col3_metric.metric("Membros Inativos", f"{inativos} 🔴"); col4_metric.metric("Status Não Definido", f"{sem_status} ⚪")

            st.divider()

            selecao_atual = set()

            st.subheader("Ações para Itens Selecionados na Lista")

            col_ativo, col_inativo = st.columns(2)

            with col_ativo:

                if st.button("🟢 Marcar como Ativos", use_container_width=True, disabled=not st.session_state.get("selecao_lista"), key="tab2_ativo"):

                    st.session_state.chaves_para_status = st.session_state.selecao_lista

                    st.session_state.novo_status = "ATIVO"; st.session_state.confirmando_status = True

            with col_inativo:

                if st.button("🔴 Marcar como Inativos", use_container_width=True, disabled=not st.session_state.get("selecao_lista"), key="tab2_inativo"):

                    st.session_state.chaves_para_status = st.session_state.selecao_lista

                    st.session_state.novo_status = "INATIVO"; st.session_state.confirmando_status = True

            if st.session_state.get('confirmando_status', False):

                novo_status = st.session_state.get('novo_status', 'DESCONHECIDO'); cor = "green" if novo_status == "ATIVO" else "red"

                st.markdown(f"Você está prestes a alterar o status de **{len(st.session_state.chaves_para_status)}** membro(s) para <span style='color:{cor}; font-weight:bold;'>{novo_status}</span>.", unsafe_allow_html=True)

                st.text_area("Adicionar Observação (opcional):", key="obs_status")

                col_confirma, col_cancela = st.columns(2)

                with col_confirma: st.button("Sim, confirmar alteração", use_container_width=True, type="primary", on_click=confirmar_mudanca_status)

                with col_cancela: st.button("Não, cancelar", use_container_width=True, on_click=cancelar_mudanca_status)

            st.divider()

            for index, membro in df_membros_tab2.iterrows():

                with st.container(border=True):

                    col_selecao, col_info = st.columns([1, 15])

                    with col_selecao:

                        if st.checkbox("", key=f"select_list_{index}", label_visibility="collapsed"):

                            selecao_atual.add((membro.get('Nome'), membro.get('Data de Nascimento')))

                    with col_info:

                        status_icon = '🟢' if str(membro.get('Status')).upper() == 'ATIVO' else '🔴' if str(membro.get('Status')).upper() == 'INATIVO' else '⚪'

                        st.subheader(f"{status_icon} {membro.get('Nome')}")

                        tipo_adm = membro.get('Forma de Admissao', 'N/A')

                        data_adm = membro.get('Data de Admissao', 'N/A')

                        st.caption(f"CPF: {membro.get('CPF', 'N/A')} | Celular: {membro.get('Celular', 'N/A')} | Admissão: {tipo_adm} em {data_adm}")

                        with st.expander("Ver Todos os Detalhes"): 

                            display_member_details(membro, f"list_{index}")

            st.session_state.selecao_lista = selecao_atual

        else:

            st.info("Nenhum membro cadastrado.")



    with tab3:

        st.header("Busca e Ações em Massa")

        col_busca1, col_busca2 = st.columns(2)

        with col_busca1: termo = st.text_input("Buscar por Nome ou CPF", key="busca_termo").strip().upper()

        with col_busca2: data_filtro = st.date_input("Buscar por Data de Nascimento", value=None, key="busca_data", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")

        df_original = pd.DataFrame(st.session_state.membros)

        if df_original.empty: st.warning("Não há membros cadastrados para exibir.")

        else:

            df_filtrado = df_original.copy()

            if 'CPF' in df_filtrado.columns: df_filtrado['CPF'] = df_filtrado['CPF'].astype(str)

            if termo:

                mask_termo = df_filtrado.apply(lambda row: termo in str(row.get('Nome', '')).upper() or termo in str(row.get('CPF', '')), axis=1)

                df_filtrado = df_filtrado[mask_termo]

            if data_filtro:

                data_filtro_str = data_filtro.strftime('%d/%m/%Y'); df_filtrado = df_filtrado[df_filtrado['Data de Nascimento'] == data_filtro_str]

            st.divider()

            st.subheader("Ações para Itens Selecionados")

            sem_selecao_busca = not st.session_state.get("selecao_busca")

            if st.button("🗑️ Excluir Selecionados", use_container_width=True, disabled=sem_selecao_busca, key="tab3_excluir", type="primary"):

                st.session_state.chaves_para_excluir = st.session_state.selecao_busca

                st.session_state.confirmando_exclusao = True

            if st.session_state.get('confirmando_exclusao', False):

                st.warning(f"Deseja realmente deletar os {len(st.session_state.chaves_para_excluir)} itens selecionados?")

                c1, c2 = st.columns(2)

                if c1.button("Sim, excluir definitivamente", use_container_width=True):

                    membros_atualizados = [m for m in st.session_state.membros if (m.get('Nome'), m.get('Data de Nascimento')) not in st.session_state.chaves_para_excluir]

                    st.session_state.membros = membros_atualizados

                    salvar_membros(membros_atualizados)

                    st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set()

                    for key in st.session_state.keys():

                        if key.startswith("select_search_"):

                            st.session_state[key] = False

                    st.success("Registros excluídos!"); st.rerun()

                if c2.button("Não, voltar", use_container_width=True):

                    st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set(); st.rerun()

            st.markdown("---")

            st.subheader("Exportar Seleção em Massa")

            EXPORT_HEADERS_BUSCA = ["Nome", "Data de Nascimento", "Forma de Admissao", "Data de Admissao", "Data de Conversao", "Celular"]

            if not df_original.empty and st.session_state.get("selecao_busca"):

                df_para_exportar = df_original[df_original.apply(lambda row: (row['Nome'], row['Data de Nascimento']) in st.session_state.selecao_busca, axis=1)]

                df_para_exportar = df_para_exportar[EXPORT_HEADERS_BUSCA]

                output_excel = BytesIO();

                with pd.ExcelWriter(output_excel, engine='openpyxl') as writer: df_para_exportar.to_excel(writer, index=False, sheet_name='Membros')

                excel_data = output_excel.getvalue()

                pdf_data = criar_pdf_exportacao_busca(df_para_exportar)

            else:

                excel_data, pdf_data = b"", b""

            col_excel, col_pdf = st.columns(2)

            with col_excel:

                st.download_button("📄 Exportar Excel", excel_data, "exportacao_membros.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=sem_selecao_busca)

            with col_pdf:

                st.download_button("📕 Exportar PDF", pdf_data, "exportacao_membros.pdf", "application/pdf", use_container_width=True, disabled=sem_selecao_busca)

            st.markdown("---")

            selecao_busca_atual = set()

            if df_filtrado.empty and (termo or data_filtro):

                st.warning("Nenhum membro encontrado com os critérios de busca especificados.")

            else:

                st.write(f"**Resultados da busca ({len(df_filtrado)}):**")

                for index, membro in df_filtrado.iterrows():

                    with st.container(border=True):

                        col_selecao_b, col_info_b = st.columns([1, 15])

                        with col_selecao_b:

                            if st.checkbox("", key=f"select_search_{index}", label_visibility="collapsed"):

                                selecao_busca_atual.add((membro.get('Nome'), membro.get('Data de Nascimento')))

                        with col_info_b:

                            status_icon = '🟢' if str(membro.get('Status')).upper() == 'ATIVO' else '🔴' if str(membro.get('Status')).upper() == 'INATIVO' else '⚪'

                            st.subheader(f"{status_icon} {membro.get('Nome')}")

                            st.caption(f"CPF: {membro.get('CPF')} | Data de Admissão: {membro.get('Data de Admissao')}")

            st.session_state.selecao_busca = selecao_busca_atual



    with tab4:

        st.header("Aniversariantes do Mês")

        if "membros" in st.session_state and st.session_state.membros:

            df_membros = pd.DataFrame(st.session_state.membros)

            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')

            df_membros.dropna(subset=['Data de Nascimento_dt'], inplace=True)

            df_membros['Mês'] = df_membros['Data de Nascimento_dt'].dt.month

            df_membros['Dia'] = df_membros['Data de Nascimento_dt'].dt.day

            meses_pt = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}

            mes_selecionado = st.selectbox("Escolha o mês para ver a lista de aniversariantes:", options=list(meses_pt.keys()), index=datetime.now().month - 1, placeholder="Selecione um mês...")

            if mes_selecionado:

                num_mes = meses_pt[mes_selecionado]

                aniversariantes_df = df_membros[df_membros['Mês'] == num_mes].sort_values(by='Dia')

                if aniversariantes_df.empty:

                    st.info("Nenhum aniversariante encontrado para este mês.")

                else:

                    st.markdown(f"### Aniversariantes de {mes_selecionado}")

                    ativos_df = aniversariantes_df[aniversariantes_df['Status'].str.upper() == 'ATIVO']

                    inativos_df = aniversariantes_df[aniversariantes_df['Status'].str.upper() == 'INATIVO']

                    outros_df = aniversariantes_df[~aniversariantes_df['Status'].str.upper().isin(['ATIVO', 'INATIVO'])]

                    df_display_cols = {'Nome': 'Nome Completo', 'Data de Nascimento': 'Data de Nascimento Completa'}

                    def display_birthday_section(title, df_section, icon):

                        if not df_section.empty:

                            st.markdown(f"#### {icon} {title}")

                            for _, row in df_section.iterrows():

                                with st.container(border=True):

                                    st.markdown(f"**Dia {row['Dia']}** - {row['Nome']}")

                            st.markdown("<br>", unsafe_allow_html=True)

                    display_birthday_section("Aniversariantes Ativos", ativos_df, "🟢")

                    display_birthday_section("Aniversariantes Inativos", inativos_df, "🔴")

                    display_birthday_section("Aniversariantes com Status Não Definido", outros_df, "⚪")

                    st.markdown("---")

                    pdf_data = criar_pdf_aniversariantes_com_status(

                        ativos_df.rename(columns=df_display_cols),

                        inativos_df.rename(columns=df_display_cols),

                        outros_df.rename(columns=df_display_cols),

                        mes_selecionado

                    )

                    st.download_button(label=f"📕 Exportar PDF de Aniversariantes de {mes_selecionado}", data=pdf_data, file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf", mime="application/pdf", use_container_width=True)

        else:

            st.info("Não há membros cadastrados para gerar a lista de aniversariantes.")



    with tab5:

        st.header("Fichas de Membros")

        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

        with col_filtro1:

            termo_busca_edicao = st.text_input("Buscar por Nome ou CPF", key="edit_search_term", placeholder="Digite para buscar...").upper()

        with col_filtro2:

            data_nasc_range = st.date_input("Filtrar por Data de Nascimento", value=(), key="edit_dob_range", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")

        with col_filtro3:

            data_adm_range = st.date_input("Filtrar por Data de Admissão", value=(), key="edit_adm_range", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")



        df_membros_edicao = pd.DataFrame(st.session_state.membros)



        if not df_membros_edicao.empty:

            if termo_busca_edicao:

                df_membros_edicao = df_membros_edicao[df_membros_edicao.apply(lambda row: termo_busca_edicao in str(row.get('Nome', '')).upper() or termo_busca_edicao in str(row.get('CPF', '')), axis=1)]

            if len(data_nasc_range) == 2:

                df_membros_edicao['Data de Nascimento_dt'] = pd.to_datetime(df_membros_edicao['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')

                df_membros_edicao = df_membros_edicao.dropna(subset=['Data de Nascimento_dt'])

                df_membros_edicao = df_membros_edicao[(df_membros_edicao['Data de Nascimento_dt'].dt.date >= data_nasc_range[0]) & (df_membros_edicao['Data de Nascimento_dt'].dt.date <= data_nasc_range[1])]

            if len(data_adm_range) == 2:

                df_membros_edicao['Data de Admissao_dt'] = pd.to_datetime(df_membros_edicao['Data de Admissao'], format='%d/%m/%Y', errors='coerce')

                df_membros_edicao = df_membros_edicao.dropna(subset=['Data de Admissao_dt'])

                df_membros_edicao = df_membros_edicao[(df_membros_edicao['Data de Admissao_dt'].dt.date >= data_adm_range[0]) & (df_membros_edicao['Data de Admissao_dt'].dt.date <= data_adm_range[1])]



            st.divider()

            

            col_h1, col_h2, col_h3, col_h4, col_h5, col_h6, col_h7 = st.columns([1, 4, 2, 2, 2, 2, 1.5])

            with col_h1: st.markdown("**Ações**")

            with col_h2: st.markdown("**Nome Completo**")

            with col_h3: st.markdown("**CPF**")

            with col_h4: st.markdown("**Nascimento**")

            with col_h5: st.markdown("**Admissão**")

            with col_h6: st.markdown("**Forma**")

            with col_h7: st.markdown("**Exportar/Imprimir**")



            for index, membro in df_membros_edicao.iterrows():

                with st.container(border=True):

                    col_edit, col_nome, col_cpf, col_nasc, col_adm, col_forma, col_pdf = st.columns([1, 4, 2, 2, 2, 2, 1.5])

                    with col_edit:

                        if st.button("✏️", key=f"edit_btn_{index}", help=f"Editar {membro.get('Nome')}"):

                            st.session_state.editing_member_key = index if st.session_state.editing_member_key != index else None

                            st.rerun()

                    

                    with col_nome:

                        status_icon = '🟢' if str(membro.get('Status', '')).upper() == 'ATIVO' else '🔴' if str(membro.get('Status', '')).upper() == 'INATIVO' else '⚪'

                        st.write(f"{status_icon} {membro.get('Nome', '')}")



                    with col_cpf: st.write(membro.get("CPF", ""))

                    with col_nasc: st.write(membro.get("Data de Nascimento", ""))

                    with col_adm: st.write(membro.get("Data de Admissao", ""))

                    with col_forma: st.write(membro.get("Forma de Admissao", ""))

                    

                    with col_pdf:

                        pdf_data = criar_pdf_ficha(membro)

                        st.download_button(

                            label="🖨️ PDF",

                            data=pdf_data,

                            file_name=f"ficha_{membro.get('Nome').replace(' ', '_').lower()}.pdf",

                            mime="application/pdf",

                            key=f"pdf_btn_{index}"

                        )



                    if st.session_state.editing_member_key == index:

                        st.session_state.editing_member_index = index

                        membro_para_editar = membro

                        

                        st.divider()

                        with st.form(key=f"edit_form_{index}"):

                            st.subheader(f"Editando dados de: {membro_para_editar.get('Nome')}")

                            

                            def get_safe_index(options, value):

                                try: return options.index(value)

                                except (ValueError, TypeError): return 0 

                            

                            estado_civil_options, forma_admissao_options, sexo_options, nacionalidade_options, uf_options, grau_instrucao_options, status_options = ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"], ["", "Batismo", "Transferência", "Aclamação"], ["M", "F"], ["", "Brasileiro(a)", "Estrangeiro(a)"], [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], ["", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo", "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"], ["Ativo", "Inativo"]



                            try:

                                data_nasc_obj = datetime.strptime(membro_para_editar.get("Data de Nascimento"), '%d/%m/%Y').date() if membro_para_editar.get("Data de Nascimento") else None

                                data_conv_obj = datetime.strptime(membro_para_editar.get("Data de Conversao"), '%d/%m/%Y').date() if membro_para_editar.get("Data de Conversao") else None

                                data_adm_obj = datetime.strptime(membro_para_editar.get("Data de Admissao"), '%d/%m/%Y').date() if membro_para_editar.get("Data de Admissao") else None

                            except (ValueError, TypeError):

                                data_nasc_obj, data_conv_obj, data_adm_obj = None, None, None



                            c1, c2 = st.columns(2)

                            with c1:

                                st.text_input("Nome", value=membro_para_editar.get("Nome"), key="edit_nome")

                                st.text_input("CPF", value=membro_para_editar.get("CPF"), key="edit_cpf")

                                st.selectbox("Estado Civil", estado_civil_options, index=get_safe_index(estado_civil_options, membro_para_editar.get("Estado Civil")), key="edit_estado_civil")

                                st.text_input("Nome do Pai", value=membro_para_editar.get("Nome do Pai"), key="edit_nome_pai")

                                st.text_input("Nome da Mãe", value=membro_para_editar.get("Nome da Mae"), key="edit_nome_mae")

                            with c2:

                                st.radio("Sexo", sexo_options, index=get_safe_index(sexo_options, membro_para_editar.get("Sexo", "M")), key="edit_sexo", horizontal=True)

                                st.date_input("Data de Nascimento", value=data_nasc_obj, key="edit_data_nasc", format="DD/MM/YYYY")

                                st.text_input("Profissão", value=membro_para_editar.get("Profissão"), key="edit_profissao")

                                st.text_input("Celular", value=membro_para_editar.get("Celular"), key="edit_celular")

                                st.selectbox("Nacionalidade", nacionalidade_options, index=get_safe_index(nacionalidade_options, membro_para_editar.get("Nacionalidade")), key="edit_nacionalidade")

                            

                            st.subheader("Endereço")

                            c3, c4, c5 = st.columns(3)

                            with c3: st.text_input("CEP", value=membro_para_editar.get("CEP"), key="edit_cep")

                            with c4: st.text_input("Endereço", value=membro_para_editar.get("Endereco"), key="edit_endereco")

                            with c5: st.text_input("Bairro", value=membro_para_editar.get("Bairro"), key="edit_bairro")

                            

                            c6, c7, c8 = st.columns(3)

                            with c6: st.text_input("Cidade", value=membro_para_editar.get("Cidade"), key="edit_cidade")

                            with c7: st.selectbox("UF (Endereço)", uf_options, index=get_safe_index(uf_options, membro_para_editar.get("UF (Endereco)")), key="edit_uf_end")

                            with c8: st.text_input("Naturalidade", value=membro_para_editar.get("Naturalidade"), key="edit_naturalidade")

                            

                            st.subheader("Informações Eclesiásticas e Adicionais")

                            c9, c10 = st.columns(2)

                            with c9:

                                st.selectbox("Forma de Admissão", forma_admissao_options, index=get_safe_index(forma_admissao_options, membro_para_editar.get("Forma de Admissao")), key="edit_forma_admissao")

                                st.selectbox("Status", status_options, index=get_safe_index(status_options, membro_para_editar.get("Status", "Ativo")), key="edit_status")

                                st.date_input("Data de Conversão", value=data_conv_obj, key="edit_data_conv", format="DD/MM/YYYY")

                                st.date_input("Data de Admissão", value=data_adm_obj, key="edit_data_adm", format="DD/MM/YYYY")

                            with c10:

                                st.selectbox("Grau de Instrução", grau_instrucao_options, index=get_safe_index(grau_instrucao_options, membro_para_editar.get("Grau de Instrução")), key="edit_grau_ins")

                                st.text_area("Observações", value=membro_para_editar.get("Observações"), key="edit_observacoes", height=155)

                            

                            st.divider()

                            col_salvar, col_cancelar = st.columns(2)

                            with col_salvar:

                                if st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):

                                    submeter_edicao_formulario()

                                    st.rerun()

                            with col_cancelar:

                                if st.form_submit_button("❌ Cancelar", use_container_width=True):

                                    st.session_state.editing_member_key = None

                                    st.rerun()

        else:

            st.info("Nenhum membro encontrado com os filtros aplicados.")
