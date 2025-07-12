# Versão 6.0 - "Futuro Fluido"
import streamlit as st
import pandas as pd
import gspread
import json
import requests
from datetime import datetime, date, timedelta
from fpdf import FPDF
from io import BytesIO
from streamlit_oauth import OAuth2Component
import jwt

# --- 1) Configuração da Página e Estilo ---
st.set_page_config(layout="wide", page_title="Fichário de Membros v6.0", page_icon=" futuristic_icon.png")

# Estilo CSS para uma aparência mais limpa
st.markdown("""
<style>
    /* Esconde o menu de hambúrguer do Streamlit e o rodapé */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Melhora a aparência dos containers */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 20px;
        background-color: rgba(255, 255, 255, 0.05);
    }
</style>
""", unsafe_allow_html=True)


# --- 2) Conexão e Gerenciamento de Dados (Backend Otimizado) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    creds_dict = json.loads(st.secrets["google_sheets"]["creds_json_str"])
    return gspread.service_account_from_dict(creds_dict)

@st.cache_data(ttl=600)
def carregar_membros_df(_client):
    try:
        ws = _client.open("Fichario_Membros_PIB_Gaibu").worksheet("Membros")
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        # Garantir que todas as colunas existam para evitar erros
        for col in HEADERS:
            if col not in df.columns:
                df[col] = ''
        df['CPF'] = df['CPF'].astype(str)
        return df
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        st.error("Planilha ou aba não encontrada. Verifique o nome em seu Google Sheets.")
        return pd.DataFrame(columns=HEADERS)

def salvar_membros_df(df):
    try:
        client = get_gspread_client()
        sh = client.open("Fichario_Membros_PIB_Gaibu")
        ws = sh.worksheet("Membros")
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear() # Limpa o cache para forçar o recarregamento dos dados
        return True
    except Exception as e:
        st.error(f"Falha ao salvar na planilha: {e}")
        return False

# --- 3) Funções de Geração de PDF (Mantidas e Otimizadas) ---
def criar_pdf_ficha(membro_series):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 10, 'Ficha Individual de Membro', 0, 1, 'C')
    # ... (a lógica interna do PDF da ficha pode ser mantida ou aprimorada)
    for campo, valor in membro_series.items():
        if valor and str(valor).strip():
            pdf.set_font("DejaVu", size=12)
            pdf.cell(50, 10, f"{campo}:", 0, 0)
            pdf.set_font("DejaVu", size=10)
            pdf.multi_cell(0, 10, str(valor), 0, 1)
    return bytes(pdf.output())

# --- 4) Definição das "Páginas" da Aplicação ---

def pagina_painel_controle(df):
    st.title("Painel de Controle")
    st.markdown("Visão geral e insights da membresia da PIB Gaibu.")
    
    total = len(df)
    ativos = len(df[df['Status'].str.upper() == 'ATIVO'])
    inativos = len(df[df['Status'].str.upper() == 'INATIVO'])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Membros", f"{total} 👥")
    col2.metric("Membros Ativos", f"{ativos} 🟢")
    col3.metric("Membros Inativos", f"{inativos} 🔴")
    
    st.divider()

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Distribuição por Admissão")
        admissao_counts = df['Forma de Admissao'].value_counts().nlargest(5)
        st.bar_chart(admissao_counts)

    with col2:
        st.subheader("Próximos Aniversariantes")
        df_aniv = df.copy()
        df_aniv['Data de Nascimento'] = pd.to_datetime(df_aniv['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
        df_aniv.dropna(subset=['Data de Nascimento'], inplace=True)
        
        hoje = datetime.now()
        df_aniv['ProximoAniversario'] = df_aniv['Data de Nascimento'].apply(
            lambda x: x.replace(year=hoje.year) if x.replace(year=hoje.year) >= hoje else x.replace(year=hoje.year + 1)
        )
        proximos = df_aniv.sort_values('ProximoAniversario').head(5)
        
        for _, row in proximos.iterrows():
            st.markdown(f"**{row['Nome']}** - {row['ProximoAniversario'].strftime('%d de %B')}")

def pagina_gerenciamento(df):
    st.title("Gerenciamento de Membros")
    
    # NOVO: Formulário de adição em um diálogo (modal)
    if st.button("➕ Adicionar Novo Membro", type="primary"):
        st.session_state.show_add_dialog = True

    if st.session_state.get("show_add_dialog", False):
        with st.dialog("Cadastrar Novo Membro"):
            with st.form("new_member_form"):
                # O formulário de cadastro viria aqui (simplificado para o exemplo)
                nome = st.text_input("Nome Completo")
                data_nasc = st.date_input("Data de Nascimento", format="DD/MM/YYYY")
                celular = st.text_input("Celular")
                status = st.selectbox("Status", ["Ativo", "Inativo"])
                
                if st.form_submit_button("Salvar Membro"):
                    novo_membro = pd.DataFrame([{"Nome": nome.upper(), "Data de Nascimento": data_nasc.strftime('%d/%m/%Y'), "Celular": celular, "Status": status}])
                    df_atualizado = pd.concat([df, novo_membro], ignore_index=True)
                    if salvar_membros_df(df_atualizado):
                        st.toast("Membro adicionado com sucesso!", icon="🎉")
                        st.session_state.show_add_dialog = False
                        st.rerun()
                    else:
                        st.error("Não foi possível salvar o membro.")

    st.divider()

    # Filtros interativos
    st.subheader("Filtros e Busca")
    termo_busca = st.text_input("Buscar por nome...", help="Digite e pressione Enter para buscar")
    status_filtro = st.multiselect("Filtrar por Status:", options=df['Status'].unique(), default=df['Status'].unique())

    df_filtrado = df[df['Status'].isin(status_filtro)]
    if termo_busca:
        df_filtrado = df_filtrado[df_filtrado['Nome'].str.contains(termo_busca, case=False, na=False)]

    st.subheader(f"Exibindo {len(df_filtrado)} Membros")

    # NOVO: Ações em massa
    with st.expander("Ações em Massa para Itens Selecionados"):
        # Lógica de seleção (usando checkboxes em um dataframe editável seria o ideal, mas complexo)
        # Mantendo o padrão de checkboxes para simplicidade
        st.warning("A seleção para ações em massa ainda está em desenvolvimento. A funcionalidade abaixo é um protótipo.")
        acao = st.selectbox("Ação:", ["", "Marcar como Ativo", "Marcar como Inativo", "Exportar para PDF", "Excluir"])
        if st.button("Executar Ação"):
            st.info(f"Ação '{acao}' seria executada nos itens selecionados.")

    # Exibição em cards
    for index, row in df_filtrado.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                status_icon = '🟢' if str(row.get('Status')).upper() == 'ATIVO' else '🔴'
                st.markdown(f"#### {status_icon} {row['Nome']}")
                st.caption(f"Admissão: {row.get('Data de Admissao', 'N/A')} | Celular: {row.get('Celular', 'N/A')}")
            with col2:
                if st.button("Ver Ficha", key=f"view_{index}"):
                    # Idealmente, abriria um diálogo com os detalhes completos
                    st.toast(f"Mostrando detalhes de {row['Nome']}.")
                if st.button("Editar", key=f"edit_{index}"):
                    # Abriria o st.dialog preenchido com os dados para edição
                    st.toast(f"Editando {row['Nome']}.")

def pagina_relatorios(df):
    st.title("Relatórios e Exportações")
    st.markdown("Gere relatórios específicos da membresia.")

    tipo_relatorio = st.selectbox("Selecione o tipo de relatório:", ["Aniversariantes do Mês"])

    if tipo_relatorio == "Aniversariantes do Mês":
        meses_pt = {
            "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, 
            "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
        }
        mes_selecionado = st.select_slider("Mês:", options=list(meses_pt.keys()), value=list(meses_pt.keys())[datetime.now().month - 1])
        
        num_mes = meses_pt[mes_selecionado]
        df_aniv = df.copy()
        df_aniv['Data de Nascimento'] = pd.to_datetime(df_aniv['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
        df_aniv.dropna(subset=['Data de Nascimento'], inplace=True)
        aniversariantes_df = df_aniv[df_aniv['Data de Nascimento'].dt.month == num_mes].sort_values(by=df_aniv['Data de Nascimento'].dt.day)

        st.subheader(f"Aniversariantes de {mes_selecionado}")
        if aniversariantes_df.empty:
            st.info("Nenhum aniversariante encontrado para este mês.")
        else:
            for _, row in aniversariantes_df.iterrows():
                st.markdown(f"**Dia {row['Data de Nascimento'].day}** - {row['Nome']}")

# --- 5) Estrutura Principal da Aplicação ---
HEADERS = ["Nome", "CPF", "Sexo", "Estado Civil", "Profissão", "Forma de Admissao", "Data de Nascimento", "Nacionalidade", "Naturalidade", "UF (Naturalidade)", "Nome do Pai", "Nome da Mae", "Nome do(a) Cônjuge", "CEP", "Endereco", "Bairro", "Cidade", "UF (Endereco)", "Grau de Instrução", "Celular", "Data de Conversao", "Data de Admissao", "Status", "Observações"]

# Lógica de Autenticação
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # Tela de Login Centralizada
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.image("logo_igreja.png", width=150) # Adicione o logo da sua igreja
        st.header("Fichário de Membros v6.0")
        st.markdown("Faça o login para acessar o sistema.")
        # Lógica de autenticação OAuth2 (simplificada)...
        if st.button("Entrar com Google", use_container_width=True):
             # A lógica real do OAuth2 seria mantida aqui
            st.session_state.authenticated = True
            st.rerun()
else:
    # --- Interface Principal Pós-Login ---
    
    # Carregamento dos dados
    client = get_gspread_client()
    df_membros = carregar_membros_df(client)

    # Navegação na Barra Lateral
    with st.sidebar:
        st.image("logo_igreja.png", width=100)
        st.header("PIB Gaibu v6.0")
        
        pagina_selecionada = st.radio(
            "Navegação",
            ["Painel de Controle", "Gerenciamento de Membros", "Relatórios"],
            key="navigation"
        )
        
        st.divider()
        st.info(f"Usuário: {st.session_state.get('username', 'Admin')}")
        if st.button("Sair"):
            st.session_state.authenticated = False
            st.rerun()

    # Renderização da página selecionada
    if pagina_selecionada == "Painel de Controle":
        pagina_painel_controle(df_membros)
    elif pagina_selecionada == "Gerenciamento de Membros":
        pagina_gerenciamento(df_membros)
    elif pagina_selecionada == "Relatórios":
        pagina_relatorios(df_membros)
