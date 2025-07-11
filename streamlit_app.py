# Versão Final e Corrigida - v5.0.1
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
st.set_page_config(layout="wide", page_title="Fichário de Membros v5.0.1")

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
    pdf.ln(5)

    def draw_status_table(pdf_obj, title, dataframe):
        if dataframe.empty:
            return
        
        pdf_obj.set_font('DejaVu', size=13)
        pdf_obj.cell(0, 10, title, 0, 1, 'L')
        pdf_obj.ln(2)
        
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
            pdf.multi_cell(0, 7, str(value), 0, 'L')
            pdf.ln(2) 
    def draw_section_header(title):
        pdf.set_font('DejaVu', size=12)
        pdf.cell(0, 10, title, 0, 1, 'L')
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)
    draw_section_header("👤 Dados Pessoais"); draw_field("CPF", membro.get("CPF")); draw_field("Data de Nascimento", membro.get("Data de Nascimento")); draw_field("Sexo", membro.get("Sexo")); draw_field("Estado Civil", membro.get("Estado Civil")); draw_field("Profissão", membro.get("Profissão")); draw_field("Celular", membro.get("Celular"))
    pdf.ln(5); draw_section_header("🏠 Endereço"); draw_field("CEP", membro.get("CEP")); draw_field("Endereço", membro.get("Endereco")); draw_field("Bairro", membro.get("Bairro")); draw_field("Cidade", membro.get("Cidade")); draw_field("UF", membro.get("UF (Endereco)"))
    pdf.ln(5); draw_section_header("👨‍👩‍👧 Filiação e Origem"); draw_field("Nome do Pai", membro.get("Nome do Pai")); draw_field("Nome da Mãe", membro.get("Nome da Mae")); draw_field("Cônjuge", membro.get("Nome do(a) Cônjuge")); draw_field("Nacionalidade", membro.get("Nacionalidade")); draw_field("Naturalidade", membro.get("Naturalidade"))
    pdf.ln(5); draw_section_header("⛪ Dados Eclesiásticos"); draw_field("Status", membro.get("Status")); draw_field("Forma de Admissão", membro.get("Forma de Admissao")); draw_field("Data de Admissão", membro.get("Data de Admissao")); draw_field("Data de Conversão", membro.get("Data de Conversao"))
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

@st.cache_data(ttl=600)
def carregar_membros():
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        records = ws.get_all_records()
        for record in records:
            record['CPF'] = str(record.get('CPF', ''))
            for header in HEADERS:
                if header not in record: record[header] = ""
        return records
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        sh = gc.create(NOME_PLANILHA); ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS)); ws.insert_row(HEADERS, 1)
        return []
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return []

def salvar_membros(lista):
    try:
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear(); ws.insert_row(HEADERS, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def buscar_cep(cep):
    cep = re.sub(r"[^\d]", "", cep)
    if len(cep) != 8: return None
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
        if resp.status_code == 200 and "erro" not in resp.json():
            data = resp.json()
            return {"endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(), "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf_end": data.get("uf", "")}
    except Exception: pass
    return None

MAP_KEYS = {"Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao", "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade", "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae", "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade", "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv", "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"}

def limpar_formulario():
    for key in MAP_KEYS.values():
        st.session_state[key] = None if "data" in key else ""
    if 'sexo' in st.session_state:
        st.session_state.sexo = "M"

def submeter_formulario():
    membros = carregar_membros()
    novo = {"Nome": str(st.session_state.get("nome", "")).strip().upper(), "CPF": str(st.session_state.get("cpf", "")).strip().upper(), "Sexo": st.session_state.get("sexo", ""), "Estado Civil": st.session_state.get("estado_civil", ""), "Profissão": str(st.session_state.get("profissao", "")).strip().upper(), "Forma de Admissao": st.session_state.get("forma_admissao", ""), "Data de Nascimento": st.session_state.data_nasc.strftime('%d/%m/%Y') if st.session_state.data_nasc else "", "Nacionalidade": st.session_state.get("nacionalidade", ""), "Naturalidade": str(st.session_state.get("naturalidade", "")).strip().upper(), "UF (Naturalidade)": st.session_state.get("uf_nat", ""), "Nome do Pai": str(st.session_state.get("nome_pai", "")).strip().upper(), "Nome da Mae": str(st.session_state.get("nome_mae", "")).strip().upper(), "Nome do(a) Cônjuge": str(st.session_state.get("conjuge", "")).strip().upper(), "CEP": str(st.session_state.get("cep", "")).strip().upper(), "Endereco": str(st.session_state.get("endereco", "")).strip().upper(), "Bairro": str(st.session_state.get("bairro", "")).strip().upper(), "Cidade": str(st.session_state.get("cidade", "")).strip().upper(), "UF (Endereco)": st.session_state.get("uf_end", ""), "Grau de Instrução": st.session_state.get("grau_ins", ""), "Celular": str(st.session_state.get("celular", "")).strip().upper(), "Data de Conversao": st.session_state.data_conv.strftime('%d/%m/%Y') if st.session_state.data_conv else "", "Data de Admissao": st.session_state.data_adm.strftime('%d/%m/%Y') if st.session_state.data_adm else "", "Status": st.session_state.get("status", ""), "Observações": st.session_state.get("observacoes", "").strip()}
    cpf_digitado = novo.get("CPF")
    is_duplicado = False
    if cpf_digitado and any(str(m.get("CPF")) == cpf_digitado for m in membros):
        st.error("Já existe um membro cadastrado com este CPF.")
    else:
        membros.append(novo)
        salvar_membros(membros)
        st.toast("Membro salvo com sucesso!", icon="🎉")
        limpar_formulario()

def init_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""
    # Inicializa chaves de confirmação se não existirem
    for key in ['confirmando_exclusao', 'confirmando_status']:
        if key not in st.session_state:
            st.session_state[key] = False

def display_member_details(membro_dict, context_prefix):
    def display_field(label, value):
        if value and str(value).strip(): st.markdown(f"**{label}:** {value}")
    st.markdown("##### 👤 Dados Pessoais"); c1, c2 = st.columns(2)
    with c1: display_field("CPF", membro_dict.get("CPF")); display_field("Sexo", membro_dict.get("Sexo")); display_field("Estado Civil", membro_dict.get("Estado Civil"))
    with c2: display_field("Data de Nascimento", membro_dict.get("Data de Nascimento")); display_field("Celular", membro_dict.get("Celular")); display_field("Profissão", membro_dict.get("Profissão"))
    st.divider(); st.markdown("##### 👨‍👩‍👧 Filiação e Origem"); c3, c4 = st.columns(2)
    with c3: display_field("Nome do Pai", membro_dict.get("Nome do Pai")); display_field("Nome da Mãe", membro_dict.get("Nome da Mae"))
    with c4: display_field("Nome do(a) Cônjuge", membro_dict.get("Nome do(a) Cônjuge")); display_field("Nacionalidade", membro_dict.get("Nacionalidade")); display_field("Naturalidade", membro_dict.get("Naturalidade"))
    st.divider(); st.markdown("##### 🏠 Endereço"); c5, c6 = st.columns(2)
    with c5: display_field("CEP", membro_dict.get("CEP")); display_field("Endereço", membro_dict.get("Endereco"))
    with c6: display_field("Bairro", membro_dict.get("Bairro")); display_field("Cidade", membro_dict.get("Cidade")); display_field("UF", membro_dict.get("UF (Endereco)"))
    st.divider(); st.markdown("##### ⛪ Dados Eclesiásticos"); c7, c8 = st.columns(2)
    with c7: display_field("Status", membro_dict.get("Status")); display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))
    with c8: display_field("Data de Admissão", membro_dict.get("Data de Admissao")); display_field("Data de Conversão", membro_dict.get("Data de Conversao"))
    st.divider(); st.markdown("##### 📝 Observações")
    obs = membro_dict.get("Observações"); 
    if obs and obs.strip(): st.text_area("", value=obs, height=100, disabled=True, label_visibility="collapsed", key=f"obs_{context_prefix}")

# --- C) Lógica Principal de Exibição ---
init_state()
if not st.session_state.get("authenticated", False):
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True); st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True); st.markdown("---")
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
    st.title("Olá!")
    col_user, col_reload, col_logout = st.columns([3, 1.2, 1])
    with col_user: st.info(f"**Usuário:** {st.session_state.get('username', '')}")
    with col_reload:
        if st.button("🔄 Sincronizar Dados", use_container_width=True):
            st.cache_data.clear(); st.rerun()
    with col_logout:
        if st.button("Sair", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
    st.divider()

    membros_data = carregar_membros()
    df_membros = pd.DataFrame(membros_data)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Lista de Membros", "Busca e Ações", "Aniversariantes", "Ficha Individual"])

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
                st.selectbox("Nacionalidade", ["", "Brasileiro(a)", "Estrangeiro(a)"], key="nacionalidade"); st.text_input("Naturalidade", key="naturalidade"); st.selectbox("UF (Naturalidade)", [""] + list(UF_CHOICES), key="uf_nat")
            st.subheader("Endereço"); col_cep, col_btn_cep, col_spacer = st.columns([1,1,2])
            with col_cep: st.text_input("CEP", key="cep")
            with col_btn_cep:
                if st.form_submit_button("🔎 Buscar CEP"):
                    dados_cep = buscar_cep(st.session_state.cep)
                    if dados_cep: st.session_state.update(dados_cep); st.toast("Endereço preenchido!", icon="🏠")
                    elif st.session_state.cep: st.warning("CEP não encontrado ou inválido.")
            c7, c8, c9, c10 = st.columns(4)
            with c7: st.text_input("Endereco", key="endereco")
            with c8: st.text_input("Bairro", key="bairro")
            with c9: st.text_input("Cidade", key="cidade")
            with c10: st.selectbox("UF (Endereco)", [""] + list(UF_CHOICES), key="uf_end")
            st.subheader("Informações Adicionais"); c11, c12, c13 = st.columns(3)
            with c11:
                st.selectbox("Grau de Instrução", ["", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo", "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"], key="grau_ins"); st.selectbox("Status", ["Ativo", "Inativo"], key="status")
            with c12:
                st.date_input("Data de Conversao", key="data_conv", value=None, min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY"); st.date_input("Data de Admissao", key="data_adm", value=None, min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
            with c13: st.text_area("Observações", key="observacoes")
            st.markdown("---"); st.form_submit_button("💾 Salvar Membro", on_click=submeter_formulario)

with tab2:
        st.header("Visão Geral da Membresia")
        membros_data = carregar_membros()
        df_membros = pd.DataFrame(membros_data)

        if not df_membros.empty:
            total_membros = len(df_membros)
            ativos = len(df_membros[df_membros['Status'].str.upper() == 'ATIVO'])
            inativos = total_membros - ativos
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Membros", f"{total_membros} 👥")
            c2.metric("Membros Ativos", f"{ativos} 🟢")
            c3.metric("Membros Inativos", f"{inativos} 🔴")
            st.divider()

            # Captura de seleções
            chaves_selecionadas = set()
            for index, row in df_membros.iterrows():
                chave_membro = (row.get('Nome'), row.get('Data de Nascimento'))
                if st.checkbox("", key=f"select_list_{index}"):
                    chaves_selecionadas.add(chave_membro)
            
            st.subheader("Ações para Itens Selecionados na Lista")
            col_ativo, col_inativo = st.columns(2)

            if col_ativo.button("🟢 Marcar como Ativos", use_container_width=True, disabled=not chaves_selecionadas):
                st.session_state.confirmando_status = True
                st.session_state.novo_status = "ATIVO"
                st.session_state.chaves_para_status = chaves_selecionadas
                st.rerun()

            if col_inativo.button("🔴 Marcar como Inativos", use_container_width=True, disabled=not chaves_selecionadas):
                st.session_state.confirmando_status = True
                st.session_state.novo_status = "INATIVO"
                st.session_state.chaves_para_status = chaves_selecionadas
                st.rerun()

            if st.session_state.get('confirmando_status'):
                st.warning(f"Alterar status de {len(st.session_state.chaves_para_status)} membro(s) para {st.session_state.novo_status}?")
                c1, c2 = st.columns(2)
                               if c1.button("Sim, confirmar", type="primary", use_container_width=True):
                    membros_atuais = carregar_membros()
                    for m in membros_atuais:
                        if (m.get('Nome'), m.get('Data de Nascimento')) in st.session_state.chaves_para_status:
                            m['Status'] = st.session_state.novo_status
                    salvar_membros(membros_atuais)
                    st.toast("Status alterado com sucesso!")
                    st.session_state.confirmando_status = False
                    st.rerun()
                if c2.button("Cancelar", use_container_width=True):
                    st.session_state.confirmando_status = False
                    st.rerun()
            
            st.divider()
            for index, row in df_membros.iterrows():
                with st.container(border=True):
                    status_icon = '🟢' if str(row.get('Status')).upper() == 'ATIVO' else '🔴' if str(row.get('Status')).upper() == 'INATIVO' else '⚪'
                    st.subheader(f"{status_icon} {row.get('Nome')}")
                    
                    # Informações adicionadas ao card
                    forma_adm = row.get('Forma de Admissao', 'N/A')
                    data_adm = row.get('Data de Admissao', 'N/A')
                    st.caption(f"CPF: {row.get('CPF', 'N/A')} | Celular: {row.get('Celular', 'N/A')} | Admissão: {forma_adm} em {data_adm}")
                    
                    with st.expander("Ver Todos os Detalhes"):
                        display_member_details(row.to_dict(), f"list_{index}")
        else:
            st.info("Nenhum membro cadastrado.")


with tab3:
        st.header("Buscar e Realizar Ações")
        termo = st.text_input("Buscar por Nome ou CPF", key="busca_termo").strip().upper()

        if termo:
            membros_data = carregar_membros()
            df_original = pd.DataFrame(membros_data)

            mask_termo = df_original.apply(
                lambda row: termo in str(row.get('Nome', '')).upper() or termo in str(row.get('CPF', '')),
                axis=1
            )
            df_filtrado = df_original[mask_termo]

            if df_filtrado.empty:
                st.warning("Nenhum membro encontrado com os critérios de busca especificados.")
            else:
                st.divider()
                st.subheader(f"Resultados da Busca: {len(df_filtrado)} membro(s) encontrado(s)")

                chaves_selecionadas_busca = set()
                for index, row in df_filtrado.iterrows():
                    chave_membro = (row.get('Nome'), row.get('Data de Nascimento'))
                    if st.checkbox(f"{row.get('Nome')} (CPF: {row.get('CPF')})", key=f"search_{index}"):
                        chaves_selecionadas_busca.add(chave_membro)
                
                st.divider()
                st.subheader("Ações para Itens Selecionados")
                col_excluir, col_excel, col_pdf = st.columns(3)

                if col_excluir.button("🗑️ Excluir Selecionados", use_container_width=True, disabled=not chaves_selecionadas_busca):
                    st.session_state.confirmando_exclusao = True
                    st.session_state.chaves_para_excluir = chaves_selecionadas_busca
                    st.rerun()

                df_para_exportar = pd.DataFrame()
                if chaves_selecionadas_busca:
                    df_para_exportar = df_original[df_original.apply(lambda row: (row['Nome'], row['Data de Nascimento']) in chaves_selecionadas_busca, axis=1)]

                output_excel = BytesIO()
                with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                    df_para_exportar.to_excel(writer, index=False, sheet_name='Membros')
                excel_data = output_excel.getvalue()
                col_excel.download_button("📄 Exportar Excel", data=excel_data, file_name="membros_selecionados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=not chaves_selecionadas_busca)

                pdf_data = criar_pdf_lista(df_para_exportar)
                col_pdf.download_button("📕 Exportar PDF", data=pdf_data, file_name="membros_selecionados.pdf", mime="application/pdf", use_container_width=True, disabled=not chaves_selecionadas_busca)

        if st.session_state.get('confirmando_exclusao'):
            chaves_para_excluir = st.session_state.get('chaves_para_excluir', set())
            st.warning(f"Deseja realmente deletar os {len(chaves_para_excluir)} itens selecionados? Esta ação não pode ser desfeita.")
            c1, c2 = st.columns(2)
            if c1.button("Sim, excluir definitivamente", use_container_width=True, type="primary"):
                membros_atuais = carregar_membros()
                membros_atualizados = [m for m in membros_atuais if (m.get('Nome'), m.get('Data de Nascimento')) not in chaves_para_excluir]
                salvar_membros(membros_atualizados)
                st.session_state.confirmando_exclusao = False
                st.success("Registros excluídos!")
                st.rerun()
            if c2.button("Não, voltar", use_container_width=True):
                st.session_state.confirmando_exclusao = False
                st.rerun()

    with tab4:
        st.header("Aniversariantes do Mês")
        if not df_membros.empty:
            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
            df_aniversariantes = df_membros.dropna(subset=['Data de Nascimento_dt']).copy()
            df_aniversariantes['Mês'] = df_aniversariantes['Data de Nascimento_dt'].dt.month
            df_aniversariantes['Dia'] = df_aniversariantes['Data de Nascimento_dt'].dt.day
            
            meses_pt = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}
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
                    # Passando o dataframe original para a função de PDF
                    pdf_data = criar_pdf_aniversariantes(aniversariantes_do_mes, mes_selecionado)
                    st.download_button(label=f"📕 Exportar PDF de {mes_selecionado}", data=pdf_data, file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf")
        else:
            st.info("Não há membros para exibir aniversariantes.")

    with tab5:
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
