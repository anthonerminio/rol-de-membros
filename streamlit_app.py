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
st.set_page_config(layout="wide", page_title="Fichário de Membros v4.3")

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
    
    st.session_state.confirmando_status = False
    st.session_state.chaves_para_status = set()
    st.session_state.obs_status = ""

def cancelar_mudanca_status():
    st.session_state.confirmando_status = False
    st.session_state.chaves_para_status = set()
    st.session_state.obs_status = ""

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
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro de Membros", "Lista de Membros", "Buscar e Excluir", "Aniversariantes do Mês", "Ficha Individual"])

    with tab1:
        # CÓDIGO COMPLETO DA ABA 1
        st.header("Cadastro de Novos Membros")
        with st.form("form_membro"):
            st.subheader("Informações Pessoais")
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Nome", key="nome")
                st.text_input("CPF", key="cpf")
                st.selectbox("Estado Civil", ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"], key="estado_civil")
                st.selectbox("Forma de Admissao", ["", "Batismo", "Transferência", "Aclamação"], key="forma_admissao")
            with c2:
                st.radio("Sexo", ["M", "F"], key="sexo", horizontal=True)
                st.date_input("Data de Nascimento", key="data_nasc", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
                st.text_input("Profissão", key="profissao")
                st.text_input("Celular", key="celular")
            st.subheader("Filiação e Origem")
            c3, c4 = st.columns(2)
            with c3:
                st.text_input("Nome do Pai", key="nome_pai")
                st.text_input("Nome da Mãe", key="nome_mae")
                st.text_input("Nome do(a) Cônjuge", key="conjuge")
            with c4:
                st.selectbox("Nacionalidade", ["", "Brasileiro(a)", "Estrangeiro(a)"], key="nacionalidade")
                st.text_input("Naturalidade", key="naturalidade")
                st.selectbox("UF (Naturalidade)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_nat")
            st.subheader("Endereço")
            col_cep, col_btn_cep, col_spacer = st.columns([1,1,2])
            with col_cep:
                st.text_input("CEP", key="cep")
            with col_btn_cep:
                if st.form_submit_button("🔎 Buscar CEP"):
                    dados_cep = buscar_cep(st.session_state.cep)
                    if dados_cep:
                        st.session_state.update(dados_cep)
                        st.toast("Endereço preenchido!", icon="🏠")
                    elif st.session_state.cep: 
                        st.warning("CEP não encontrado ou inválido.")
            c7, c8, c9, c10 = st.columns(4)
            with c7:
                st.text_input("Endereco", key="endereco")
            with c8:
                st.text_input("Bairro", key="bairro")
            with c9:
                st.text_input("Cidade", key="cidade")
            with c10:
                st.selectbox("UF (Endereco)", [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"], key="uf_end")
            st.subheader("Informações Adicionais")
            c11, c12, c13 = st.columns(3)
            with c11:
                st.selectbox("Grau de Instrução", ["", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo", "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"], key="grau_ins")
                st.selectbox("Status", ["Ativo", "Inativo"], key="status")
            with c12:
                st.date_input("Data de Conversao", key="data_conv", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
                st.date_input("Data de Admissao", key="data_adm", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
            with c13:
                 st.text_area("Observações", key="observacoes")
            
            st.markdown("---")
            st.form_submit_button("💾 Salvar Membro", on_click=submeter_formulario)

    with tab2:
        # CÓDIGO DA ABA 2 COM NOVO LAYOUT
        st.header("Visão Geral da Membresia")
        
        if "membros" in st.session_state and st.session_state.membros:
            df_membros_tab2 = pd.DataFrame(st.session_state.membros)
            total_membros = len(df_membros_tab2)
            ativos = len(df_membros_tab2[df_membros_tab2['Status'].str.upper() == 'ATIVO'])
            inativos = len(df_membros_tab2[df_membros_tab2['Status'].str.upper() == 'INATIVO'])
            sem_status = total_membros - ativos - inativos

            col1_metric, col2_metric, col3_metric, col4_metric = st.columns(4)
            col1_metric.metric("Total de Membros", f"{total_membros} 👥")
            col2_metric.metric("Membros Ativos", f"{ativos} 🟢")
            col3_metric.metric("Membros Inativos", f"{inativos} 🔴")
            col4_metric.metric("Status Não Definido", f"{sem_status} ⚪")
            st.divider()

            if st.session_state.get('confirmando_status', False):
                novo_status = st.session_state.get('novo_status', 'DESCONHECIDO')
                cor = "green" if novo_status == "ATIVO" else "red"
                with st.expander(f"**⚠️ CONFIRMAÇÃO DE MUDANÇA DE STATUS**", expanded=True):
                    st.markdown(f"Você está prestes a alterar o status de **{len(st.session_state.chaves_para_status)}** membro(s) para <span style='color:{cor}; font-weight:bold;'>{novo_status}</span>.", unsafe_allow_html=True)
                    st.text_area("Adicionar Observação (opcional):", key="obs_status")
                    col_confirma, col_cancela = st.columns(2)
                    with col_confirma:
                        st.button("Sim, confirmar alteração", use_container_width=True, type="primary", on_click=confirmar_mudanca_status)
                    with col_cancela:
                        st.button("Não, cancelar", use_container_width=True, on_click=cancelar_mudanca_status)

            # Novo Layout em Cartões
            st.info("A lista de membros agora é exibida em cartões. Use a caixa de seleção em cada cartão para alterar o status em massa.")
            
            membros_selecionados_chaves = set()
            for index, membro in df_membros_tab2.iterrows():
                with st.container(border=True):
                    col_info, col_selecao = st.columns([10, 1])
                    
                    with col_info:
                        status_icon = '🟢' if str(membro.get('Status')).upper() == 'ATIVO' else '🔴' if str(membro.get('Status')).upper() == 'INATIVO' else '⚪'
                        st.subheader(f"{status_icon} {membro.get('Nome')}")
                        st.caption(f"CPF: {membro.get('CPF')} | Celular: {membro.get('Celular')}")
                    
                    with col_selecao:
                        selecionado = st.checkbox("Selecionar", key=f"select_{index}")
                        if selecionado:
                            membros_selecionados_chaves.add((membro.get('Nome'), membro.get('Data de Nascimento')))
                    
                    with st.expander("Ver Todos os Detalhes"):
                        # Reutiliza a função de display da ficha individual
                        def display_field_card(label, value):
                            if value and str(value).strip():
                                st.markdown(f"**{label}:** {value}")
                        
                        campos = {k: membro.get(k) for k in HEADERS if k not in ['Nome', 'CPF', 'Celular', 'Status']}
                        col_detalhes1, col_detalhes2 = st.columns(2)
                        
                        itens_metade = (len(campos) + 1) // 2
                        itens_col1 = dict(list(campos.items())[:itens_metade])
                        itens_col2 = dict(list(campos.items())[itens_metade:])
                        
                        with col_detalhes1:
                            for chave, valor in itens_col1.items():
                                display_field_card(chave, valor)
                        with col_detalhes2:
                            for chave, valor in itens_col2.items():
                                display_field_card(chave, valor)

            st.divider()
            
            sem_selecao = not bool(membros_selecionados_chaves)
            col1_act, col2_act, col3_act = st.columns([2,2,3])
            with col1_act:
                if st.button("🟢 Marcar Selecionados como Ativos", use_container_width=True, disabled=sem_selecao):
                    st.session_state.chaves_para_status = membros_selecionados_chaves
                    st.session_state.novo_status = "ATIVO"
                    st.session_state.confirmando_status = True
                    st.rerun()
            with col2_act:
                if st.button("🔴 Marcar Selecionados como Inativos", use_container_width=True, disabled=sem_selecao):
                    st.session_state.chaves_para_status = membros_selecionados_chaves
                    st.session_state.novo_status = "INATIVO"
                    st.session_state.confirmando_status = True
                    st.rerun()
            with col3_act:
                if st.button("🔄 Recarregar Dados"): 
                    st.session_state.membros = carregar_membros()
                    st.rerun()
        else:
            st.info("Nenhum membro cadastrado.")


    with tab3:
        # CÓDIGO DA ABA 3 (COMPLETO E FUNCIONAL)
        st.header("Buscar, Exportar e Excluir Membros")
        col_busca1, col_busca2 = st.columns(2)
        with col_busca1:
            termo = st.text_input("Buscar por Nome ou CPF", key="busca_termo").strip().upper()
        with col_busca2:
            data_filtro = st.date_input("Buscar por Data de Nascimento", value=None, key="busca_data", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
        
        st.info("Filtre para refinar a lista, ou selecione diretamente na lista completa abaixo para Excluir ou Exportar.")
        
        df_original = pd.DataFrame(st.session_state.membros)
        if df_original.empty:
            st.warning("Não há membros cadastrados para exibir.")
        else:
            df_filtrado = df_original.copy()
            if 'CPF' in df_filtrado.columns: df_filtrado['CPF'] = df_filtrado['CPF'].astype(str)
            if termo:
                mask_termo = df_filtrado.apply(lambda row: termo in str(row.get('Nome', '')).upper() or termo in str(row.get('CPF', '')), axis=1)
                df_filtrado = df_filtrado[mask_termo]
            if data_filtro:
                data_filtro_str = data_filtro.strftime('%d/%m/%Y')
                df_filtrado = df_filtrado[df_filtrado['Data de Nascimento'] == data_filtro_str]

            if df_filtrado.empty:
                st.warning("Nenhum membro encontrado com os critérios de busca especificados.")
            else:
                df_formatado = formatar_datas(df_filtrado.copy(), ["Data de Nascimento", "Data de Conversao", "Data de Admissao"]).reindex(columns=HEADERS)
                df_formatado.insert(0, "Selecionar", False)
                edited_df = st.data_editor(df_formatado, disabled=[col for col in df_formatado.columns if col != "Selecionar"], hide_index=True, use_container_width=True, key="editor_selecao")
                registros_selecionados = edited_df[edited_df["Selecionar"] == True]
                sem_selecao = registros_selecionados.empty
                st.markdown("---")
                col1_del, col2_del, col3_del = st.columns(3)
                if st.session_state.get('confirmando_exclusao', False):
                    with st.expander("⚠️ CONFIRMAÇÃO DE EXCLUSÃO ⚠️", expanded=True):
                        st.warning(f"Deseja realmente deletar os {len(st.session_state.chaves_para_excluir)} itens selecionados?")
                        c1, c2 = st.columns(2)
                        if c1.button("Sim, excluir definitivamente", use_container_width=True, type="primary"):
                            membros_atualizados = [m for m in st.session_state.membros if (m.get('Nome'), m.get('Data de Nascimento')) not in st.session_state.chaves_para_excluir]
                            st.session_state.membros = membros_atualizados
                            salvar_membros(membros_atualizados)
                            st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set()
                            st.success("Registros excluídos!")
                            st.rerun()
                        if c2.button("Não, voltar", use_container_width=True):
                            st.session_state.confirmando_exclusao, st.session_state.chaves_para_excluir = False, set()
                            st.rerun()
                else:
                    with col1_del:
                        if st.button("🗑️ Excluir Registros Selecionados", use_container_width=True, disabled=sem_selecao):
                            st.session_state.chaves_para_excluir = set((row['Nome'], row['Data de Nascimento']) for _, row in registros_selecionados.iterrows())
                            st.session_state.confirmando_exclusao = True
                            st.rerun()
                    with col2_del:
                        df_excel = registros_selecionados.drop(columns=['Selecionar'])
                        output_excel = BytesIO()
                        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                            df_excel.to_excel(writer, index=False, sheet_name='Membros')
                        excel_data = output_excel.getvalue()
                        st.download_button(label="📄 Exportar Excel (.xlsx)", data=excel_data, file_name="membros_selecionados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=sem_selecao)
                    with col3_del:
                        df_pdf = registros_selecionados.drop(columns=['Selecionar'])
                        pdf_data = criar_pdf_lista(df_pdf)
                        st.download_button(label="📕 Exportar PDF (.pdf)", data=pdf_data, file_name="membros_selecionados.pdf", mime="application/pdf", use_container_width=True, disabled=sem_selecao)

    with tab4:
        st.header("Aniversariantes do Mês")
        if "membros" in st.session_state and st.session_state.membros:
            df_membros = pd.DataFrame(st.session_state.membros)
            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
            df_membros.dropna(subset=['Data de Nascimento_dt'], inplace=True)
            df_membros['Mês'] = df_membros['Data de Nascimento_dt'].dt.month
            df_membros['Dia'] = df_membros['Data de Nascimento_dt'].dt.day
            meses_pt = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}
            mes_selecionado = st.selectbox("Escolha o mês para ver a lista de aniversariantes:", options=list(meses_pt.keys()), index=None, placeholder="Selecione um mês...")
            if mes_selecionado:
                num_mes = meses_pt[mes_selecionado]
                aniversariantes_df = df_membros[df_membros['Mês'] == num_mes].sort_values('Dia')
                st.markdown(f"### Aniversariantes de {mes_selecionado}")
                if aniversariantes_df.empty:
                    st.info("Nenhum aniversariante encontrado para este mês.")
                else:
                    df_display = aniversariantes_df[['Dia', 'Nome', 'Data de Nascimento']].copy()
                    df_display.rename(columns={'Nome': 'Nome Completo', 'Data de Nascimento': 'Data de Nascimento Completa'}, inplace=True)
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    st.markdown("---")
                    pdf_data = criar_pdf_aniversariantes(df_display, mes_selecionado)
                    st.download_button(label=f"📕 Exportar PDF de {mes_selecionado}", data=pdf_data, file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf", mime="application/pdf")
        else:
            st.info("Não há membros cadastrados para gerar a lista de aniversariantes.")

    with tab5:
        st.header("Gerar Ficha Individual de Membro")
        if "membros" in st.session_state and st.session_state.membros:
            lista_nomes = [""] + sorted([m.get("Nome", "") for m in st.session_state.membros if m.get("Nome")])
            membro_selecionado_nome = st.selectbox(
                "Selecione ou digite o nome do membro para gerar a ficha:", 
                options=lista_nomes,
                placeholder="Selecione um membro...",
                index=0
            )
            if membro_selecionado_nome:
                membro_dict = next((m for m in st.session_state.membros if m.get("Nome") == membro_selecionado_nome), None)
                if membro_dict:
                    st.divider()
                    
                    def display_field(label, value):
                        if value and str(value).strip():
                            st.markdown(f"**{label}:** {value}")

                    st.subheader(f"Ficha de: {membro_dict['Nome']}")
                    st.markdown("---")

                    st.markdown("##### 👤 Dados Pessoais e Contato")
                    col1, col2 = st.columns(2)
                    with col1:
                        display_field("CPF", membro_dict.get("CPF"))
                        display_field("Sexo", membro_dict.get("Sexo"))
                        display_field("Estado Civil", membro_dict.get("Estado Civil"))
                    with col2:
                        display_field("Data de Nascimento", membro_dict.get("Data de Nascimento"))
                        display_field("Celular", membro_dict.get("Celular"))
                        display_field("Profissão", membro_dict.get("Profissão"))

                    st.divider()
                    st.markdown("##### ⛪ Dados Eclesiásticos")
                    col3, col4 = st.columns(2)
                    with col3:
                        display_field("Status", membro_dict.get("Status"))
                        display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))
                    with col4:
                        display_field("Data de Admissão", membro_dict.get("Data de Admissao"))
                        display_field("Data de Conversão", membro_dict.get("Data de Conversao"))

                    st.divider()
                    st.markdown("##### 🏠 Endereço")
                    col5, col6 = st.columns(2)
                    with col5:
                        display_field("CEP", membro_dict.get("CEP"))
                        display_field("Endereço", membro_dict.get("Endereco"))
                    with col6:
                        display_field("Bairro", membro_dict.get("Bairro"))
                        display_field("Cidade", membro_dict.get("Cidade"))
                        display_field("UF", membro_dict.get("UF (Endereco)"))
                    
                    st.divider()
                    
                    if st.button("📄 Exportar Ficha como PDF", key="export_ficha_pdf"):
                        with st.spinner("Gerando PDF da ficha..."):
                            pdf_data = criar_pdf_ficha(membro_dict)
                            st.download_button(
                                label="Clique para Baixar o PDF",
                                data=pdf_data,
                                file_name=f"ficha_{membro_dict['Nome'].replace(' ', '_').lower()}.pdf",
                                mime="application/pdf"
                            )
        else:
            st.warning("Não há membros cadastrados para gerar fichas.")
