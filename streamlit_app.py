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
st.set_page_config(layout="wide", page_title="Fichário de Membros PIB Gaibu")

# --- A) Parâmetros de Login Google (lendo dos Segredos) ---
try:
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
except (KeyError, FileNotFoundError):
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()


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

try:
    creds_json_str = st.secrets["google_sheets"]["creds_json_str"]
    creds_dict = json.loads(creds_json_str)
except (KeyError, FileNotFoundError):
    st.error("As credenciais do Google Sheets não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()


@st.cache_resource(ttl=3600)
def get_client(creds):
    return gspread.service_account_from_dict(creds)

gc = get_client(creds_dict)

# Lista completa de cabeçalhos
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
    if "inicializado" not in st.session_state:
        st.session_state.inicializado = True
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.membros = carregar_membros()
        st.session_state.cep_busca_ok = False
        st.session_state.confirmando_exclusao = False
        st.session_state.cpfs_para_excluir = set()
        
        # Lista de chaves completa para o session state
        form_keys = [
            "nome", "cpf", "sexo", "estado_civil", "profissao", "forma_admissao", 
            "data_nasc", "nacionalidade", "naturalidade", "uf_nat", "nome_pai", 
            "nome_mae", "conjuge", "cep", "endereco", "bairro", "cidade", "uf_end", 
            "grau_ins", "celular", "data_conv", "data_adm", "status", "observacoes"
        ]
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
        token = oauth2.authorize_button(
            "Entrar com Google",
            key="google_login",
            redirect_uri=GOOGLE_REDIRECT_URI,
            scope="openid email profile"
        )
        if token:
            try:
                id_token = token.get("id_token")
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
else:
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

    with tab1:
        st.header("Cadastro de Novos Membros")
        with st.form("form_membro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Nome completo", key="nome")
                st.text_input("CPF", key="cpf")
                st.radio("Sexo", ["M", "F"], key="sexo", horizontal=True)
                st.selectbox("Estado Civil", ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"], key="estado_civil")
                st.text_input("Profissão", key="profissao")
                st.selectbox("Forma de Admissão", ["", "Batismo", "Transferência", "Aclamação"], key="forma_admissao")
                st.date_input("Data de Nascimento", key="data_nasc", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
            with c2:
                st.selectbox("Nacionalidade", ["", "Brasileiro(a)", "Estrangeiro(a)"], key="nacionalidade")
                st.text_input("Naturalidade", key="naturalidade")
                st.selectbox("UF (Naturalidade)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_nat")
                st.text_input("Nome do Pai", key="nome_pai")
                st.text_input("Nome da Mãe", key="nome_mae")
                st.text_input("Cônjuge", key="conjuge")
                cep_input = st.text_input("CEP", key="cep")
                if st.form_submit_button("🔎 Buscar CEP"):
                    dados_cep = buscar_cep(cep_input)
                    if dados_cep:
                        st.session_state.endereco, st.session_state.bairro, st.session_state.cidade, st.session_state.uf_end = dados_cep["endereco"], dados_cep["bairro"], dados_cep["cidade"], dados_cep["uf"]
                        st.success("Endereço preenchido!")
                    elif cep_input: st.warning("CEP não encontrado ou inválido.")
                st.text_area("Endereço", key="endereco", height=80)
                st.text_input("Bairro", key="bairro")
                st.text_input("Cidade", key="cidade")
                st.selectbox("UF (Endereço)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_end")
            st.markdown("---")
            c3, c4, c5 = st.columns(3)
            with c3:
                st.selectbox("Grau de Instrução", ["", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo", "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"], key="grau_ins")
                st.text_input("Celular", key="celular")
            with c4:
                st.date_input("Data de Conversão", key="data_conv", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
                st.date_input("Data de Admissão", key="data_adm", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
                st.selectbox("Status", ["Ativo", "Inativo"], key="status")
            with c5:
                st.text_area("Observações", key="observacoes", height=80)
            if st.form_submit_button("💾 Salvar Membro"):
                novo = {h: st.session_state.get(h.lower().replace(" (", "_").replace(")", "").replace(" ", "_"), "") for h in HEADERS}
                for k, v in novo.items():
                    if isinstance(v, str): novo[k] = v.strip().upper()
                
                datas = ["Data de Nascimento", "Data de Conversao", "Data de Admissao"]
                for d in datas:
                    if st.session_state.get(d.lower().replace(" ", "_")):
                        novo[d] = st.session_state[d.lower().replace(" ", "_")].strftime('%d/%m/%Y')
                    else:
                        novo[d] = ""

                if novo["CPF"] and any(m["CPF"] == novo["CPF"] for m in st.session_state.membros):
                    st.error("Já existe um membro cadastrado com este CPF.")
                else:
                    st.session_state.membros.append(novo)
                    salvar_membros(st.session_state.membros)
                    st.success("Membro salvo com sucesso!")

    with tab2:
        st.header("Lista de Membros")
        if st.session_state.membros:
            df2 = pd.DataFrame(st.session_state.membros)
            if 'Status' in df2.columns:
                df2['Situação'] = df2['Status'].apply(lambda s: '🟢' if str(s).upper() == 'ATIVO' else '🔴' if str(s).upper() == 'INATIVO' else '⚪')
                df2 = df2[ ['Situação'] + [col for col in df2.columns if col != 'Situação'] ]
            df2_formatado = formatar_datas(df2.copy(), ["Data de Nascimento", "Data de Conversao", "Data de Admissao"])
            st.dataframe(df2_formatado, use_container_width=True, hide_index=True)
            if st.button("🔄 Recarregar Dados"): st.rerun()
        else:
            st.info("Nenhum membro cadastrado.")

    with tab3:
        st.header("Buscar, Exportar e Excluir Membros")
        col_busca1, col_busca2 = st.columns(2)
        with col_busca1:
            termo = st.text_input("Buscar por Nome ou CPF", key="busca_termo").strip().upper()
        with col_busca2:
            data_filtro = st.date_input("Buscar por Data de Nascimento", value=None, key="busca_data", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
        
        df_original = pd.DataFrame(st.session_state.membros)
        df_filtrado = df_original.copy()
        
        if termo:
            mask_termo = df_filtrado.apply(lambda row: termo in str(row['Nome']).upper() or termo in str(row['CPF']), axis=1)
            df_filtrado = df_filtrado[mask_termo]
        if data_filtro:
            data_filtro_str = data_filtro.strftime('%d/%m/%Y')
            df_filtrado = df_filtrado[df_filtrado['Data de Nascimento'] == data_filtro_str]

        if termo or data_filtro:
            if not df_filtrado.empty:
                df_formatado = formatar_datas(df_filtrado.copy(), ["Data de Nascimento", "Data de Conversao", "Data de Admissao"])
                df_formatado.insert(0, "Selecionar", False)
                edited_df = st.data_editor(df_formatado, disabled=[col for col in df_formatado.columns if col != "Selecionar"], hide_index=True, use_container_width=True, key="editor_selecao")
                registros_selecionados = edited_df[edited_df["Selecionar"] == True]
                sem_selecao = registros_selecionados.empty
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                if st.session_state.get('confirmando_exclusao', False):
                    with st.expander("⚠️ CONFIRMAÇÃO DE EXCLUSÃO ⚠️", expanded=True):
                        st.warning(f"Deseja realmente deletar os {len(st.session_state.cpfs_para_excluir)} itens selecionados?")
                        c1, c2 = st.columns(2)
                        if c1.button("Sim, excluir definitivamente", use_container_width=True, type="primary"):
                            membros_atualizados = [m for m in st.session_state.membros if m.get("CPF") not in st.session_state.cpfs_para_excluir]
                            st.session_state.membros = membros_atualizados
                            salvar_membros(membros_atualizados)
                            st.session_state.confirmando_exclusao = False
                            st.session_state.cpfs_para_excluir = set()
                            st.success("Registros excluídos!")
                            st.rerun()
                        if c2.button("Não, voltar", use_container_width=True):
                            st.session_state.confirmando_exclusao = False
                            st.session_state.cpfs_para_excluir = set()
                            st.rerun()
                else:
                    with col1:
                        if st.button("🗑️ Excluir Registros Selecionados", use_container_width=True, disabled=sem_selecao):
                            st.session_state.cpfs_para_excluir = set(registros_selecionados["CPF"])
                            st.session_state.confirmando_exclusao = True
                            st.rerun()
                    with col2:
                        df_excel = registros_selecionados.drop(columns=['Selecionar'])
                        output_excel = BytesIO()
                        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                            df_excel.to_excel(writer, index=False, sheet_name='Membros')
                        excel_data = output_excel.getvalue()
                        st.download_button(label="📄 Exportar Excel (.xlsx)", data=excel_data, file_name="membros_selecionados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=sem_selecao)
                    with col3:
                        df_pdf = registros_selecionados.drop(columns=['Selecionar'])
                        pdf_data = criar_pdf(df_pdf)
                        st.download_button(label="📕 Exportar PDF (.pdf)", data=pdf_data, file_name="membros_selecionados.pdf", mime="application/pdf", use_container_width=True, disabled=sem_selecao)
            else:
                st.info("Nenhum membro encontrado com os critérios de busca.")
        else:
            st.info("Utilize um dos filtros acima para iniciar a busca.")
