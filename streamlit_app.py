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
                return {"endereco": f"{data.get('logradouro', '')}", "bairro": data.get("bairro", ""), "cidade": data.get("localidade", ""), "uf": data.get("uf", "")}
    except Exception:
        pass
    return None

MAP_KEYS = {"Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao", "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade", "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae", "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade", "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv", "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"}

def limpar_formulario():
    """Limpa os campos do formulário no session_state."""
    for key in MAP_KEYS.values():
        if "data" in key:
            st.session_state[key] = None
        else:
            st.session_state[key] = ""
    st.session_state.sexo = "M"

def init_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""

    if st.session_state.authenticated and "membros" not in st.session_state:
        st.session_state.membros = carregar_membros()
        st.session_state.confirmando_exclusao = False
        st.session_state.cpfs_para_excluir = set()
        
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
        with st.form("form_membro", clear_on_submit=False):
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
            c5, c6 = st.columns([1, 3])
            with c5:
                cep_input = st.text_input("CEP", key="cep")
            # CORREÇÃO 1: Botão de buscar CEP agora é um st.form_submit_button
            with c6:
                buscar_cep_btn = st.form_submit_button("🔎 Buscar CEP")
            
            if buscar_cep_btn:
                dados_cep = buscar_cep(st.session_state.cep)
                if dados_cep:
                    st.session_state.update(dados_cep)
                    st.success("Endereço preenchido!")
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
            btn_salvar = st.form_submit_button("💾 Salvar Membro")

        if btn_salvar:
            novo = {}
            for header, key in MAP_KEYS.items():
                valor = st.session_state.get(key, "")
                if isinstance(valor, date): novo[header] = valor.strftime('%d/%m/%Y')
                elif isinstance(valor, str): novo[header] = valor.strip().upper()
                else: novo[header] = valor
            
            cpf_digitado = novo.get("CPF")
            # CORREÇÃO 2: Lógica de validação do CPF ajustada
            is_duplicado = False
            if cpf_digitado: # Apenas checa duplicidade se um CPF foi fornecido
                is_duplicado = any(m.get("CPF") == cpf_digitado for m in st.session_state.membros)

            if is_duplicado:
                st.error("Já existe um membro cadastrado com este CPF.")
            else:
                st.session_state.membros.append(novo)
                salvar_membros(st.session_state.membros)
                st.success("Membro salvo com sucesso!")
                limpar_formulario()
                st.rerun()

    with tab2:
        st.header("Lista de Membros")
        if "membros" in st.session_state and st.session_state.membros:
            df2 = pd.DataFrame(st.session_state.membros).reindex(columns=HEADERS)
            if 'Status' in df2.columns:
                df2['Situação'] = df2['Status'].apply(lambda s: '🟢' if str(s).upper() == 'ATIVO' else '🔴' if str(s).upper() == 'INATIVO' else '⚪')
                colunas_ordenadas = ['Situação'] + [col for col in HEADERS if col in df2.columns]
                df2 = df2[colunas_ordenadas]
            df2_formatado = formatar_datas(df2.copy(), ["Data de Nascimento", "Data de Conversao", "Data de Admissao"])
            st.dataframe(df2_formatado, use_container_width=True, hide_index=True)
            if st.button("🔄 Recarregar Dados"): 
                st.session_state.membros = carregar_membros()
                st.rerun()
        else:
            st.info("Nenhum membro cadastrado.")

    with tab3:
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
