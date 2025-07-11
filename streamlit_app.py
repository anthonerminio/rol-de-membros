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
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()


# --- Funções Auxiliares ---
def criar_pdf(df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 8)
    cols = df.columns
    col_widths = {'Nome': 45, 'CPF': 25, 'Data de Nascimento': 22, 'Celular': 25, 'Estado Civil': 22, 'Profissão': 25}
    line_height = pdf.font_size * 2.5
    for col in cols:
        width = col_widths.get(col, 18)
        pdf.cell(width, line_height, col, border=1, ln=0, align='C')
    pdf.ln(line_height)
    pdf.set_font('helvetica', '', 7)
    for index, row in df.iterrows():
        for col in cols:
            width = col_widths.get(col, 18)
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
        nome = str(row['Nome Completo']).encode('latin-1', 'replace').decode('latin-1')
        data_nasc = str(row['Data de Nascimento Completa']).encode('latin-1', 'replace').decode('latin-1')
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
                return {"endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(), "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf_end": data.get("uf", "")}
    except Exception:
        pass
    return None

MAP_KEYS = {"Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao", "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade", "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae", "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade", "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv", "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"}

def limpar_formulario():
    for key in MAP_KEYS.values():
        if "data" in key:
            st.session_state[key] = None
        else:
            st.session_state[key] = ""
    st.session_state.sexo = "M"

def submeter_formulario():
    novo = {}
    for header, key in MAP_KEYS.items():
        valor = st.session_state.get(key, "")
        if isinstance(valor, date): novo[header] = valor.strftime('%d/%m/%Y')
        elif isinstance(valor, str): novo[header] = valor.strip().upper()
        else: novo[header] = valor
    
    cpf_digitado = novo.get("CPF")
    is_duplicado = False
    if cpf_digitado:
        is_duplicado = any(str(m.get("CPF")) == cpf_digitado for m in st.session_state.membros)

    if is_duplicado:
        st.error("Já existe um membro cadastrado com este CPF.")
    else:
        st.session_state.membros.append(novo)
        salvar_membros(st.session_state.membros)
        st.success("Membro salvo com sucesso!")
        limpar_formulario()

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
        
        for key in MAP_KEYS.values():
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
    
    tab1, tab2, tab3, tab4 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir", "Aniversariantes do Mês"])

    with tab1:
        st.header("Cadastro de Novos Membros")
        with st.form("form_membro"):
            # ... (código da aba 1 inalterado) ...

    with tab2:
        st.header("Lista de Membros")
        
        # Lógica de Confirmação de Mudança de Status
        if st.session_state.get('confirmando_status', False):
            novo_status = st.session_state.get('novo_status', 'DESCONHECIDO')
            cor = "green" if novo_status == "ATIVO" else "red"
            with st.expander(f"**⚠️ CONFIRMAÇÃO DE MUDANÇA DE STATUS**", expanded=True):
                st.markdown(f"Você está prestes a alterar o status de **{len(st.session_state.chaves_para_status)}** membro(s) para <span style='color:{cor}; font-weight:bold;'>{novo_status}</span>.", unsafe_allow_html=True)
                st.text_area("Adicionar Observação (será adicionada ao campo 'Observações' dos membros selecionados):", key="obs_status")
                
                col_confirma, col_cancela = st.columns(2)
                with col_confirma:
                    if st.button("Sim, confirmar alteração", use_container_width=True, type="primary"):
                        chaves_para_atualizar = st.session_state.chaves_para_status
                        novo_status_val = st.session_state.novo_status
                        obs_adicional = st.session_state.obs_status
                        data_hoje = date.today().strftime("%d/%m/%Y")

                        for membro in st.session_state.membros:
                            chave_membro = (membro.get('Nome'), membro.get('Data de Nascimento'))
                            if chave_membro in chaves_para_atualizar:
                                membro['Status'] = novo_status_val
                                obs_existente = membro.get('Observações', '')
                                nova_obs = f"[{data_hoje}] STATUS ALTERADO PARA {novo_status_val}. {obs_adicional}".strip()
                                membro['Observações'] = f"{obs_existente}\n{nova_obs}".strip()
                        
                        salvar_membros(st.session_state.membros)
                        st.success("Status dos membros alterado com sucesso!")
                        
                        # Limpar estados de confirmação
                        st.session_state.confirmando_status = False
                        st.session_state.chaves_para_status = set()
                        st.session_state.obs_status = ""
                        st.rerun()

                with col_cancela:
                    if st.button("Não, cancelar", use_container_width=True):
                        st.session_state.confirmando_status = False
                        st.session_state.chaves_para_status = set()
                        st.session_state.obs_status = ""
                        st.rerun()

        if "membros" in st.session_state and st.session_state.membros:
            df_membros = pd.DataFrame(st.session_state.membros).reindex(columns=HEADERS)
            
            df_display = df_membros.copy()
            if 'Status' in df_display.columns:
                df_display['Situação'] = df_display['Status'].apply(lambda s: '🟢' if str(s).upper() == 'ATIVO' else '🔴' if str(s).upper() == 'INATIVO' else '⚪')
                colunas_ordenadas = ['Situação'] + [col for col in HEADERS if col in df_display.columns]
                df_display = df_display[colunas_ordenadas]
            
            df_display_formatado = formatar_datas(df_display, ["Data de Nascimento", "Data de Conversao", "Data de Admissao"])
            
            df_display_formatado.insert(0, "Selecionar", False)
            edited_df = st.data_editor(
                df_display_formatado,
                disabled=[col for col in df_display_formatado.columns if col != "Selecionar"],
                hide_index=True,
                use_container_width=True,
                key="editor_status"
            )

            registros_selecionados = edited_df[edited_df["Selecionar"] == True]
            sem_selecao = registros_selecionados.empty
            
            st.markdown("---")
            col1, col2, col_spacer = st.columns([1, 1, 2])

            with col1:
                if st.button("🟢 Marcar Selecionados como Ativos", use_container_width=True, disabled=sem_selecao):
                    chaves = set()
                    for _, row in registros_selecionados.iterrows():
                        chaves.add((row['Nome'], row['Data de Nascimento']))
                    st.session_state.chaves_para_status = chaves
                    st.session_state.novo_status = "ATIVO"
                    st.session_state.confirmando_status = True
                    st.rerun()
            with col2:
                if st.button("🔴 Marcar Selecionados como Inativos", use_container_width=True, disabled=sem_selecao):
                    chaves = set()
                    for _, row in registros_selecionados.iterrows():
                        chaves.add((row['Nome'], row['Data de Nascimento']))
                    st.session_state.chaves_para_status = chaves
                    st.session_state.novo_status = "INATIVO"
                    st.session_state.confirmando_status = True
                    st.rerun()

            if st.button("🔄 Recarregar Dados"): 
                st.session_state.membros = carregar_membros()
                st.rerun()
        else:
            st.info("Nenhum membro cadastrado.")


    with tab3:
        # Código da aba 3 (inalterado)
        st.header("Buscar, Exportar e Excluir Membros")
        # ...

    with tab4:
        # Código da aba 4 (inalterado)
        st.header("Aniversariantes do Mês")
        # ...
