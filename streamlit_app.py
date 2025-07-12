# Versão 6.1 - Completa e Funcional
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

# --- 1) Configuração da Página e Constantes ---
st.set_page_config(layout="wide", page_title="Fichário de Membros v6.1")
HEADERS = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge", "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)", "Grau de Instrução", "Celular", "Data de Conversao", "Data de Admissao", "Status", "Observações"]
UF_LISTA = [""] + ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

# --- 2) Conexão e Gerenciamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    creds_dict = json.loads(st.secrets["google_sheets"]["creds_json_str"])
    return gspread.service_account_from_dict(creds_dict)

@st.cache_data(ttl=600)
def carregar_membros_df(_client):
    try:
        ws = _client.open("Fichario_Membros_PIB_Gaibu").worksheet("Membros")
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=HEADERS)
        df = pd.DataFrame(records)
        for col in HEADERS:
            if col not in df.columns:
                df[col] = ''
        df['CPF'] = df['CPF'].astype(str)
        return df[HEADERS]
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        st.error("Planilha ou aba 'Membros' não encontrada.")
        return pd.DataFrame(columns=HEADERS)

def salvar_membros_df(df):
    try:
        client = get_gspread_client()
        sh = client.open("Fichario_Membros_PIB_Gaibu")
        ws = sh.worksheet("Membros")
        df_to_save = df.reindex(columns=HEADERS).fillna('')
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.astype(str).values.tolist(), value_input_option='USER_ENTERED')
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Falha ao salvar na planilha: {e}")
        return False

def buscar_cep(cep):
    cep = re.sub(r"[^\d]", "", cep)
    if len(cep) != 8: return None
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
        if resp.status_code == 200:
            data = resp.json()
            if "erro" not in data:
                return {"form_endereco": data.get("logradouro", ""), "form_bairro": data.get("bairro", ""), "form_cidade": data.get("localidade", ""), "form_uf_end": data.get("uf", "")}
    except Exception: pass
    return None

# --- 3) Funções de Geração de PDF ---
# (Lógicas de PDF da v5.9, comprovadamente funcionais)
def criar_pdf_ficha(membro_series):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 10, 'Ficha Individual de Membro', 0, 1, 'C')
    pdf.set_font("DejaVu", size=14)
    pdf.cell(0, 10, membro_series.get("Nome", ""), 0, 1, 'C')
    pdf.ln(5)

    def draw_field(label, value):
        if pd.notna(value) and str(value).strip():
            pdf.set_font('DejaVu', '', size=10)
            pdf.cell(50, 7, f"{label}:", 0, 0, 'L')
            pdf.multi_cell(0, 7, str(value), 0, 'L')
            pdf.ln(2)

    def draw_section_header(title):
        pdf.set_font('DejaVu', '', size=12)
        pdf.cell(0, 10, title, 0, 1, 'L')
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    draw_section_header("👤 Dados Pessoais"); draw_field("CPF", membro_series.get("CPF")); draw_field("Data de Nascimento", membro_series.get("Data de Nascimento")); draw_field("Celular", membro_series.get("Celular"))
    draw_section_header("⛪ Dados Eclesiásticos"); draw_field("Status", membro_series.get("Status")); draw_field("Forma de Admissão", membro_series.get("Forma de Admissao")); draw_field("Data de Admissão", membro_series.get("Data de Admissao"))
    if pd.notna(membro_series.get("Observações")) and str(membro_series.get("Observações")).strip():
        draw_section_header("📝 Observações"); draw_field("", membro_series.get("Observações"))
    return bytes(pdf.output())

def criar_pdf_aniversariantes(df_aniv, mes_nome):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 10, f'Aniversariantes de {mes_nome}', 0, 1, 'C')
    pdf.ln(10)
    for _, row in df_aniv.iterrows():
        pdf.set_font('DejaVu', '', size=11)
        pdf.cell(0, 8, f"Dia {row['Data de Nascimento'].day} - {row['Nome']}", 0, 1, 'L')
    return bytes(pdf.output())

# --- 4) Definição das "Páginas" da Aplicação ---

def pagina_painel_controle(df):
    st.title("Painel de Controle")
    st.markdown("Visão geral e insights da membresia da PIB Gaibu.")
    
    if df.empty:
        st.info("👋 Bem-vindo! Ainda não há membros cadastrados. Adicione o primeiro na página 'Membros'.")
        return

    total = len(df)
    ativos = len(df[df['Status'].astype(str).str.upper() == 'ATIVO'])
    inativos = total - ativos

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Membros", f"{total} 👥")
    col2.metric("Membros Ativos", f"{ativos} 🟢")
    col3.metric("Membros Inativos", f"{inativos} 🔴")
    
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribuição por Admissão")
        admissao_counts = df['Forma de Admissao'].value_counts().nlargest(5)
        if not admissao_counts.empty:
            st.bar_chart(admissao_counts)

    with col2:
        st.subheader("Próximos Aniversariantes")
        df_aniv = df.copy()
        df_aniv['Data de Nascimento'] = pd.to_datetime(df_aniv['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
        df_aniv.dropna(subset=['Data de Nascimento'], inplace=True)
        
        hoje = datetime.now()
        df_aniv['ProximoAniversario'] = df_aniv['Data de Nascimento'].apply(lambda x: x.replace(year=hoje.year) if x.replace(year=hoje.year) >= hoje else x.replace(year=hoje.year + 1))
        proximos = df_aniv.sort_values('ProximoAniversario').head(5)
        
        for _, row in proximos.iterrows():
            st.markdown(f"**{row['Nome']}** - {row['ProximoAniversario'].strftime('%d de %B')}")

def pagina_membros(df):
    st.title("Gerenciamento de Membros")

    if st.button("➕ Adicionar Novo Membro", type="primary"):
        st.session_state.show_add_dialog = True

    if st.session_state.get("show_add_dialog", False):
        with st.dialog("Cadastrar Novo Membro", width="large"):
            with st.form("new_member_form"):
                st.subheader("Informações Pessoais")
                c1,c2 = st.columns(2)
                with c1:
                    nome = st.text_input("Nome*")
                    cpf = st.text_input("CPF")
                    estado_civil = st.selectbox("Estado Civil", ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"])
                    profissao = st.text_input("Profissão")
                with c2:
                    data_nasc = st.date_input("Data de Nascimento", value=None, min_value=date(1910,1,1), format="DD/MM/YYYY")
                    sexo = st.radio("Sexo", ["M", "F"], horizontal=True)
                    celular = st.text_input("Celular")
                st.subheader("Endereço")
                c3, c4 = st.columns([1,3])
                with c3:
                    cep = st.text_input("CEP", key="form_cep")
                with c4:
                    if st.form_submit_button("Buscar CEP"):
                        dados_cep = buscar_cep(st.session_state.form_cep)
                        if dados_cep: st.session_state.update(dados_cep)

                endereco=st.text_input("Endereço", key="form_endereco"); bairro=st.text_input("Bairro", key="form_bairro")
                c5,c6 = st.columns(2); cidade=c5.text_input("Cidade", key="form_cidade"); uf_end=c6.selectbox("UF", UF_LISTA, key="form_uf_end")
                
                st.subheader("Dados Eclesiásticos")
                c7,c8=st.columns(2); forma_adm=c7.selectbox("Forma de Admissão", ["", "Batismo", "Transferência", "Aclamação"]); data_adm=c8.date_input("Data de Admissão", value=None, format="DD/MM/YYYY")
                status=st.selectbox("Status", ["Ativo", "Inativo"])
                observacoes = st.text_area("Observações")

                if st.form_submit_button("Salvar Membro"):
                    if not nome:
                        st.error("O campo 'Nome' é obrigatório.")
                    else:
                        novo_membro_data = {h:'' for h in HEADERS}
                        novo_membro_data.update({"Nome": nome.upper(), "CPF": cpf, "Estado Civil": estado_civil, "Profissão": profissao, "Data de Nascimento": data_nasc.strftime('%d/%m/%Y') if data_nasc else "", "Sexo": sexo, "Celular": celular, "CEP": cep, "Endereco": endereco, "Bairro": bairro, "Cidade": cidade, "UF (Endereco)": uf_end, "Forma de Admissao": forma_adm, "Data de Admissao": data_adm.strftime('%d/%m/%Y') if data_adm else "", "Status": status, "Observações": observacoes})
                        df_atualizado = pd.concat([df, pd.DataFrame([novo_membro_data])], ignore_index=True)
                        if salvar_membros_df(df_atualizado):
                            st.toast("Membro adicionado!", icon="🎉"); st.session_state.show_add_dialog = False; st.rerun()

    st.divider()
    st.subheader("Buscar e Realizar Ações")
    termo_busca = st.text_input("Buscar por Nome ou CPF...", key="termo_busca")
    df_filtrado = df[df.apply(lambda row: termo_busca.lower() in str(row['Nome']).lower() or termo_busca in str(row['CPF']), axis=1)] if termo_busca else df

    # Ações em Massa
    st.markdown("**Ações para itens selecionados na lista abaixo:**")
    selecao_indices = st.session_state.get("selecao_membros", [])
    col1, col2, col3 = st.columns(3)
    
    with col1:
        novo_status = st.selectbox("Mudar status para:", ["", "Ativo", "Inativo"], label_visibility="collapsed")
        if st.button("Aplicar Status", use_container_width=True, disabled=(not novo_status or not selecao_indices)):
            for idx in selecao_indices:
                df.loc[idx, 'Status'] = novo_status
            if salvar_membros_df(df):
                st.toast(f"Status de {len(selecao_indices)} membro(s) alterado!", icon="👍"); st.session_state.selecao_membros = []; st.rerun()

    with col2:
        if st.button("🗑️ Excluir Selecionados", use_container_width=True, disabled=not selecao_indices, type="primary"):
            st.session_state.confirmando_exclusao = True
    
    if st.session_state.get("confirmando_exclusao"):
        st.warning(f"Deseja realmente excluir {len(selecao_indices)} membro(s)? Esta ação não pode ser desfeita.")
        c1, c2 = st.columns(2)
        if c1.button("Confirmar Exclusão", use_container_width=True):
            df.drop(selecao_indices, inplace=True)
            if salvar_membros_df(df):
                st.toast("Membros excluídos!", icon="✅"); st.session_state.confirmando_exclusao=False; st.session_state.selecao_membros = []; st.rerun()
        if c2.button("Cancelar", use_container_width=True):
            st.session_state.confirmando_exclusao = False; st.rerun()

    # Exibição dos membros com checkboxes
    st.subheader(f"Exibindo {len(df_filtrado)} de {len(df)} membros")
    selecao_atual = []
    for index, row in df_filtrado.iterrows():
        with st.container(border=True):
            col_check, col_info = st.columns([1, 10])
            with col_check:
                if st.checkbox("", key=f"select_{index}", value=(index in selecao_indices)):
                    selecao_atual.append(index)
            with col_info:
                status_icon = '🟢' if str(row.get('Status')).upper() == 'ATIVO' else '🔴'
                st.markdown(f"**{row['Nome']}** {status_icon}")
                st.caption(f"Admissão: {row.get('Data de Admissao', 'N/A')} | Celular: {row.get('Celular', 'N/A')}")
    st.session_state.selecao_membros = selecao_atual

def pagina_aniversariantes(df):
    st.title("Relatório de Aniversariantes")
    if df.empty: return

    meses_pt = {m: i for i, m in enumerate(["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], 1)}
    mes_selecionado = st.selectbox("Escolha o mês:", options=list(meses_pt.keys()), index=datetime.now().month - 1)
    
    num_mes = meses_pt[mes_selecionado]
    df['Data de Nascimento'] = pd.to_datetime(df['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
    aniversariantes_df = df[df['Data de Nascimento'].dt.month == num_mes].dropna(subset=['Data de Nascimento']).sort_values(by=df['Data de Nascimento'].dt.day)

    st.subheader(f"Aniversariantes de {mes_selecionado} ({len(aniversariantes_df)})")
    if not aniversariantes_df.empty:
        st.download_button("Exportar PDF", criar_pdf_aniversariantes(aniversariantes_df, mes_selecionado), f"aniversariantes_{mes_selecionado.lower()}.pdf", "application/pdf")
        for _, row in aniversariantes_df.iterrows():
            st.markdown(f"- **Dia {row['Data de Nascimento'].day}** - {row['Nome']}")

def pagina_ficha_individual(df):
    st.title("Gerar Ficha Individual")
    if df.empty: return

    nomes = ["Selecione um membro..."] + sorted(df['Nome'].unique().tolist())
    membro_selecionado = st.selectbox("Buscar membro:", options=nomes)

    if membro_selecionado != "Selecione um membro...":
        membro_data = df[df['Nome'] == membro_selecionado].iloc[0]
        st.divider(); st.header(membro_data['Nome'])
        for campo, valor in membro_data.items():
            if pd.notna(valor) and str(valor).strip(): st.markdown(f"**{campo}:** {valor}")
        st.divider()
        st.download_button("📄 Exportar Ficha como PDF", criar_pdf_ficha(membro_data), f"ficha_{membro_data['Nome'].replace(' ', '_').lower()}.pdf", "application/pdf", use_container_width=True)

# --- 5) Estrutura Principal e Autenticação ---
def init_session_state():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    if "show_add_dialog" not in st.session_state: st.session_state.show_add_dialog = False
    if "selecao_membros" not in st.session_state: st.session_state.selecao_membros = []
    if "confirmando_exclusao" not in st.session_state: st.session_state.confirmando_exclusao = False

init_session_state()

if not st.session_state.authenticated:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.header("Fichário de Membros v6.1")
        st.markdown("Acesse o sistema de gerenciamento da PIB Gaibu.")
        try:
            oauth2 = OAuth2Component(client_id=st.secrets["google_oauth"]["client_id"], client_secret=st.secrets["google_oauth"]["client_secret"], authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth", token_endpoint="https://oauth2.googleapis.com/token")
            token_response = oauth2.authorize_button("Entrar com Google", key="google_login", redirect_uri="https://pibgaibu.streamlit.app", scope="openid email profile", use_container_width=True)
            if token_response:
                user_info = jwt.decode(token_response['token']['id_token'], options={"verify_signature": False})
                if user_info.get("email") in st.secrets["google_oauth"]["emails_permitidos"]:
                    st.session_state.authenticated = True; st.session_state.username = user_info.get("email"); st.rerun()
                else:
                    st.error("Acesso não autorizado para este e-mail.")
        except Exception as e:
            st.error(f"Erro de autenticação: Verifique suas credenciais no Streamlit Secrets.")
else:
    client = get_gspread_client()
    df_membros = carregar_membros_df(client)

    with st.sidebar:
        st.header("PIB Gaibu v6.1")
        pagina_selecionada = st.radio("Navegação", ["Painel de Controle", "Membros", "Aniversariantes", "Ficha Individual"], key="navigation")
        st.divider()
        st.info(f"Usuário: {st.session_state.get('username')}")
        if st.button("Sair"):
            st.session_state.clear(); st.rerun()

    # Roteamento de Páginas
    if pagina_selecionada == "Painel de Controle":
        pagina_painel_controle(df_membros)
    elif pagina_selecionada == "Membros":
        pagina_membros(df_membros)
    elif pagina_selecionada == "Aniversariantes":
        pagina_aniversariantes(df_membros)
    elif pagina_selecionada == "Ficha Individual":
        pagina_ficha_individual(df_membros)
