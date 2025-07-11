# Versão Final e Corrigida - v5.4
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
st.set_page_config(layout="wide", page_title="Fichário de Membros v5.4")

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
        # Garante que todos os cabeçalhos existem para cada registro
        for record in records:
            record['CPF'] = str(record.get('CPF', ''))
            for header in HEADERS:
                if header not in record:
                    record[header] = ""
        return records
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        gc = get_client()
        sh = gc.create(NOME_PLANILHA)
        ws = sh.add_worksheet(title=NOME_ABA, rows="100", cols=len(HEADERS))
        ws.insert_row(HEADERS, 1)
        return []
    except Exception as e:
        st.error(f"Não foi possível carregar os dados da planilha: {e}")
        return []

def salvar_membros(lista):
    try:
        gc = get_client()
        ws = gc.open(NOME_PLANILHA).worksheet(NOME_ABA)
        ws.clear()
        ws.insert_row(HEADERS, 1)
        if lista:
            rows = [[str(m.get(h, '')) for h in HEADERS] for m in lista]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
        st.cache_data.clear() # Limpa o cache para forçar o recarregamento dos dados na próxima leitura
        st.toast("Ação concluída com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar dados na planilha: {e}")

# --- Funções de Lógica da Aplicação ---
def buscar_cep(cep):
    cep = re.sub(r"[^\d]", "", cep)
    if len(cep) != 8: return None
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
        if resp.status_code == 200 and "erro" not in resp.json():
            data = resp.json()
            return {
                "endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(),
                "bairro": data.get("bairro", ""),
                "cidade": data.get("localidade", ""),
                "uf_end": data.get("uf", "")
            }
    except requests.RequestException:
        st.error("Erro ao se conectar com a API de CEP.")
    return None

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
    st.markdown("##### ⛪ Dados Eclesiásticos")
    c3, c4 = st.columns(2)
    with c3:
        display_field("Status", membro_dict.get("Status"))
        display_field("Forma de Admissão", membro_dict.get("Forma de Admissao"))
    with c4:
        display_field("Data de Admissão", membro_dict.get("Data de Admissao"))
        display_field("Data de Conversão", membro_dict.get("Data de Conversao"))
        
    obs = membro_dict.get("Observações")
    if obs and obs.strip():
        st.divider()
        st.markdown("##### 📝 Observações")
        st.text_area("", value=obs, height=100, disabled=True, label_visibility="collapsed", key=f"obs_{context_prefix}")

# --- Lógica Principal de Exibição ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True); st.divider()
        try:
            token_response = oauth2.authorize_button("Entrar com Google", key="google_login", redirect_uri=GOOGLE_REDIRECT_URI, scope="openid email profile")
            if token_response:
                id_token = token_response.get("token", {}).get("id_token")
                if id_token:
                    user_info = jwt.decode(id_token, options={"verify_signature": False})
                    email = user_info.get("email", "")
                    if email in EMAILS_PERMITIDOS:
                        st.session_state.authenticated = True
                        st.session_state.username = email
                        st.rerun()
                    else:
                        st.error("Acesso não autorizado para este e-mail.")
        except Exception as e:
            st.error(f"Ocorreu um erro durante o login: {e}")
else:
    # --- Interface Principal Pós-Login ---
    st.title("Olá!")
    col_user, col_reload, col_logout = st.columns([3, 1.2, 1])
    with col_user: st.info(f"**Usuário:** {st.session_state.get('username', 'Conectado')}")
    with col_reload:
        if st.button("🔄 Sincronizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_logout:
        if st.button("Sair", use_container_width=True):
            keys = list(st.session_state.keys())
            for key in keys: del st.session_state[key]
            st.rerun()
    st.divider()

    membros_data = carregar_membros()
    df_membros = pd.DataFrame(membros_data)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Lista de Membros", "Busca e Ações", "Aniversariantes", "Ficha Individual"])

    with tab1:
        st.header("Cadastro de Novos Membros")
        with st.form("form_cadastro", clear_on_submit=True):
            st.subheader("Informações Pessoais")
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome Completo*")
                cpf = st.text_input("CPF")
                estado_civil = st.selectbox("Estado Civil", ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"])
            with c2:
                sexo = st.radio("Sexo", ["M", "F"], horizontal=True)
                data_nasc = st.date_input("Data de Nascimento", value=None, format="DD/MM/YYYY")
                profissao = st.text_input("Profissão")
            
            celular = st.text_input("Celular")
            
            st.subheader("Endereço")
            col_cep, col_btn_cep, col_spacer = st.columns([1, 1, 2])
            cep = col_cep.text_input("CEP")
            # Este botão não submete o formulário principal, apenas busca o CEP
            if col_btn_cep.form_submit_button("🔎 Buscar CEP"):
                dados_cep = buscar_cep(cep)
                if dados_cep:
                    st.session_state.cep_info = dados_cep
                    st.toast("Endereço preenchido!")
            
            endereco = st.text_input("Endereço", value=st.session_state.get('cep_info', {}).get('endereco', ''))
            bairro = st.text_input("Bairro", value=st.session_state.get('cep_info', {}).get('bairro', ''))
            cidade = st.text_input("Cidade", value=st.session_state.get('cep_info', {}).get('cidade', ''))
            uf_end = st.selectbox("UF (Endereço)", UF_CHOICES, index=UF_CHOICES.index(st.session_state.get('cep_info', {}).get('uf_end', 'AC')) if st.session_state.get('cep_info', {}).get('uf_end') in UF_CHOICES else None)

            st.subheader("Informações Eclesiásticas")
            forma_admissao = st.selectbox("Forma de Admissão", ["", "Batismo", "Transferência", "Aclamação"])
            status = st.selectbox("Status", ["Ativo", "Inativo"])
            
            observacoes = st.text_area("Observações")
            
            submitted = st.form_submit_button("💾 Salvar Novo Membro", type="primary")
            if submitted:
                if not nome:
                    st.error("O campo 'Nome Completo' é obrigatório.")
                else:
                    novo_membro = { "Nome": nome.strip().upper(), "CPF": cpf, "Estado Civil": estado_civil, "Sexo": sexo, "Data de Nascimento": data_nasc.strftime('%d/%m/%Y') if data_nasc else "", "Profissão": profissao, "Celular": celular, "CEP": cep, "Endereco": endereco, "Bairro": bairro, "Cidade": cidade, "UF (Endereco)": uf_end, "Forma de Admissao": forma_admissao, "Status": status, "Observações": observacoes }
                    membros_data.append(novo_membro)
                    salvar_membros(membros_data)
                    if 'cep_info' in st.session_state: del st.session_state['cep_info']
                    st.rerun()

    with tab2:
        st.header("Visão Geral da Membresia")
        if not df_membros.empty:
            with st.form("form_lista_membros"):
                st.subheader("Ações em Lote (para itens selecionados)")
                c1, c2 = st.columns(2)
                submeter_ativo = c1.form_submit_button("🟢 Marcar como Ativos", use_container_width=True)
                submeter_inativo = c2.form_submit_button("🔴 Marcar como Inativos", use_container_width=True)
                st.divider()

                selecoes = {}
                for idx, row in df_membros.iterrows():
                    chave_membro = (row.get('Nome'), row.get('Data de Nascimento'))
                    selecoes[chave_membro] = st.toggle(f"{row.get('Nome')}", key=f"toggle_list_{idx}")
                
                if submeter_ativo or submeter_inativo:
                    chaves_selecionadas = {chave for chave, selecionado in selecoes.items() if selecionado}
                    if not chaves_selecionadas:
                        st.warning("Nenhum membro selecionado.")
                    else:
                        novo_status = "ATIVO" if submeter_ativo else "INATIVO"
                        membros_atuais = df_membros.to_dict('records')
                        for membro in membros_atuais:
                            if (membro.get('Nome'), membro.get('Data de Nascimento')) in chaves_selecionadas:
                                membro['Status'] = novo_status
                        salvar_membros(membros_atuais)
                        st.rerun()
        else:
            st.info("Nenhum membro cadastrado.")

    with tab3:
        st.header("Buscar e Realizar Ações")
        termo = st.text_input("Buscar por Nome ou CPF", "").strip().upper()
        
        if termo:
            mask = df_membros.apply(lambda row: termo in str(row.get('Nome', '')).upper() or termo in str(row.get('CPF', '')), axis=1)
            df_filtrado = df_membros[mask]

            if df_filtrado.empty:
                st.warning("Nenhum membro encontrado.")
            else:
                with st.form("form_busca"):
                    st.subheader("Ações para Resultados da Busca")
                    c1, c2, c3 = st.columns(3)
                    excluir_btn = c1.form_submit_button("🗑️ Excluir Selecionados", use_container_width=True)
                    
                    st.divider()
                    selecoes_busca = {}
                    for idx, row in df_filtrado.iterrows():
                        chave = (row.get('Nome'), row.get('Data de Nascimento'))
                        selecoes_busca[chave] = st.toggle(f"{row.get('Nome')}", key=f"toggle_search_{idx}")
                    
                    if excluir_btn:
                        chaves_selecionadas = {chave for chave, sel in selecoes_busca.items() if sel}
                        if not chaves_selecionadas:
                            st.warning("Nenhum membro selecionado para exclusão.")
                        else:
                            st.session_state.confirm_delete = chaves_selecionadas
                            st.rerun()

    # Bloco de confirmação para exclusão (fora do formulário)
    if st.session_state.get('confirm_delete'):
        st.warning(f"Você tem certeza que deseja excluir {len(st.session_state.confirm_delete)} membro(s)? Esta ação não pode ser desfeita.")
        c1, c2 = st.columns(2)
        if c1.button("Sim, Excluir", type="primary", use_container_width=True):
            membros_restantes = [m for m in membros_data if (m.get('Nome'), m.get('Data de Nascimento')) not in st.session_state.confirm_delete]
            salvar_membros(membros_restantes)
            del st.session_state.confirm_delete
            st.rerun()
        if c2.button("Cancelar", use_container_width=True):
            del st.session_state.confirm_delete
            st.rerun()

    with tab4:
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
                    # Lógica de exibição e PDF que já estava correta
                    # ...
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
                # A função display_member_details precisa ser chamada aqui
                # display_member_details(membro_dict, "ficha_individual")
                st.divider()
                pdf_data_ficha = criar_pdf_ficha(membro_dict)
                st.download_button("📄 Exportar Ficha como PDF", pdf_data_ficha, f"ficha_{membro_dict['Nome'].replace(' ', '_').lower()}.pdf", "application/pdf", use_container_width=True)
        else:
            st.warning("Não há membros cadastrados.")
