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
from PIL import Image, ImageDraw, ImageFont
import matplotlib.font_manager

st.set_page_config(layout="wide", page_title="Fichário de Membros v4.1")

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

def criar_imagem_ficha(membro):
    largura, altura = 2480, 1748
    img = Image.new('RGB', (largura, altura), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        caminho_fonte = matplotlib.font_manager.findfont('DejaVu Sans')
        fonte_titulo_grande = ImageFont.truetype(caminho_fonte, 90)
        fonte_subtitulo = ImageFont.truetype(caminho_fonte, 60)
        fonte_label = ImageFont.truetype(caminho_fonte, 45)
        fonte_valor = ImageFont.truetype(caminho_fonte, 45)
    except:
        fonte_titulo_grande, fonte_subtitulo, fonte_label, fonte_valor = [ImageFont.load_default()]*4

    draw.rectangle([(0, 0), (largura, 180)], fill=(14, 17, 23))
    draw.text((80, 50), "Ficha Individual de Membro - PIB Gaibu", fill='white', font=fonte_titulo_grande)

    def draw_field(x, y, label, value):
        if value and str(value).strip():
            draw.text((x, y), label, fill=(100, 116, 139), font=fonte_label)
            draw.text((x + 500, y), str(value), fill='black', font=fonte_valor)
            return 85
        return 0

    y_pos1, y_pos2 = 280, 280
    x_pos1, x_pos2 = 100, largura / 2 + 100

    draw.text((x_pos1, y_pos1), "👤 Dados Pessoais", fill='black', font=fonte_subtitulo)
    y_pos1 += 100
    y_pos1 += draw_field(x_pos1, y_pos1, "Nome:", membro.get("Nome") or membro.get("nome", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "CPF:", membro.get("CPF") or membro.get("cpf", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "Data de Nascimento:", membro.get("Data de Nascimento") or membro.get("data_nasc", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "Sexo:", membro.get("Sexo") or membro.get("sexo", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "Estado Civil:", membro.get("Estado Civil") or membro.get("estado_civil", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "Profissão:", membro.get("Profissão") or membro.get("profissao", ""))
    y_pos1 += draw_field(x_pos1, y_pos1, "Celular:", membro.get("Celular") or membro.get("celular", ""))

    draw.text((x_pos2, y_pos2), "👨‍👩‍👧 Filiação e Origem", fill='black', font=fonte_subtitulo)
    y_pos2 += 100
    y_pos2 += draw_field(x_pos2, y_pos2, "Nome do Pai:", membro.get("Nome do Pai") or membro.get("nome_pai", ""))
    y_pos2 += draw_field(x_pos2, y_pos2, "Nome da Mãe:", membro.get("Nome da Mae") or membro.get("nome_mae", ""))
    y_pos2 += draw_field(x_pos2, y_pos2, "Cônjuge:", membro.get("Nome do(a) Cônjuge") or membro.get("conjuge", ""))
    y_pos2 += draw_field(x_pos2, y_pos2, "Nacionalidade:", membro.get("Nacionalidade") or membro.get("nacionalidade", ""))
    y_pos2 += draw_field(x_pos2, y_pos2, "Naturalidade:", membro.get("Naturalidade") or membro.get("naturalidade", ""))
    y_pos2 += draw_field(x_pos2, y_pos2, "UF (Naturalidade):", membro.get("UF (Naturalidade)") or membro.get("uf_nat", ""))

    y_final = max(y_pos1, y_pos2) + 40
    draw.line([(80, y_final), (largura - 80, y_final)], fill='lightgray', width=3)
    y_final += 40
    draw.text((x_pos1, y_final), "🏠 Endereço", fill='black', font=fonte_subtitulo)
    y_final += 100
    y_final += draw_field(x_pos1, y_final, "CEP:", membro.get("CEP") or membro.get("cep", ""))
    y_final += draw_field(x_pos1, y_final, "Endereço:", membro.get("Endereco") or membro.get("endereco", ""))
    y_final += draw_field(x_pos1, y_final, "Bairro:", membro.get("Bairro") or membro.get("bairro", ""))
    y_final += draw_field(x_pos1, y_final, "Cidade:", membro.get("Cidade") or membro.get("cidade", ""))
    y_final += draw_field(x_pos1, y_final, "UF:", membro.get("UF (Endereco)") or membro.get("uf_end", ""))

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

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
                return {
                    "endereco": f"{data.get('logradouro', '')} {data.get('complemento', '')}".strip(),
                    "bairro": data.get("bairro", ""),
                    "cidade": data.get("localidade", ""),
                    "uf_end": data.get("uf", "")
                }
    except Exception:
        pass
    return None

MAP_KEYS = {
    "Nome": "nome", "CPF": "cpf", "Sexo": "sexo", "Estado Civil": "estado_civil", "Profissão": "profissao",
    "Forma de Admissao": "forma_admissao", "Data de Nascimento": "data_nasc", "Nacionalidade": "nacionalidade",
    "Naturalidade": "naturalidade", "UF (Naturalidade)": "uf_nat", "Nome do Pai": "nome_pai", "Nome da Mae": "nome_mae",
    "Nome do(a) Cônjuge": "conjuge", "CEP": "cep", "Endereco": "endereco", "Bairro": "bairro", "Cidade": "cidade",
    "UF (Endereco)": "uf_end", "Grau de Instrução": "grau_ins", "Celular": "celular", "Data de Conversao": "data_conv",
    "Data de Admissao": "data_adm", "Status": "status", "Observações": "observacoes"
}

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
                st.selectbox("Grau de Instrução", [
                    "", "Fundamental Incompleto", "Fundamental Completo", "Médio Incompleto", "Médio Completo",
                    "Superior Incompleto", "Superior Completo", "Pós-graduação", "Mestrado", "Doutorado"
                ], key="grau_ins")
                st.selectbox("Status", ["Ativo", "Inativo"], key="status")
            with c12:
                st.date_input("Data de Conversao", key="data_conv", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
                st.date_input("Data de Admissao", key="data_adm", min_value=date(1910, 1, 1), max_value=date(2030, 12, 31), format="DD/MM/YYYY")
            with c13:
                 st.text_area("Observações", key="observacoes")
            st.markdown("---")
            st.form_submit_button("💾 Salvar Membro", on_click=submeter_formulario)

    with tab2:
        st.header("Visão Geral da Membresia")
        if "membros" in st.session_state and st.session_state.membros:
            df_membros = pd.DataFrame(st.session_state.membros)
            total_membros = len(df_membros)
            ativos = len(df_membros[df_membros['Status'].str.upper() == 'ATIVO'])
            inativos = len(df_membros[df_membros['Status'].str.upper() == 'INATIVO'])
            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Membros", f"{total_membros} 👥")
            col2.metric("Membros Ativos", f"{ativos} 🟢")
            col3.metric("Membros Inativos", f"{inativos} 🔴")
            st.markdown("---")
            # ... (lógica de status)
            df_display = df_membros.copy()
            df_display['Situação'] = df_display['Status'].apply(lambda s: '🟢' if str(s).upper() == 'ATIVO' else '🔴' if str(s).upper() == 'INATIVO' else '⚪')
            colunas_ordenadas = ['Situação'] + HEADERS
            df_display_formatado = formatar_datas(df_display.copy(), ["Data de Nascimento", "Data de Conversao", "Data de Admissao"])
            df_display_formatado = df_display_formatado[colunas_ordenadas]
            df_display_formatado.insert(0, "Selecionar", False)
            edited_df = st.data_editor(df_display_formatado, disabled=[col for col in df_display_formatado.columns if col != "Selecionar"], hide_index=True, use_container_width=True, key="editor_status")
            # ... (botões de status)
        else:
            st.info("Nenhum membro cadastrado.")

    with tab3:
        st.header("Buscar, Exportar e Excluir Membros")
        # ... (código completo da aba 3)

    with tab4:
        st.header("Aniversariantes do Mês")
        if "membros" in st.session_state and st.session_state.membros:
            df_membros = pd.DataFrame(st.session_state.membros)
            # Garantir que as colunas existam, ajuste nomes se necessário
            if 'Data de Nascimento' not in df_membros.columns and 'data_nasc' in df_membros.columns:
                df_membros['Data de Nascimento'] = df_membros['data_nasc']
            if 'Nome' not in df_membros.columns and 'nome' in df_membros.columns:
                df_membros['Nome'] = df_membros['nome']
            df_membros['Data de Nascimento_dt'] = pd.to_datetime(df_membros['Data de Nascimento'], format='%d/%m/%Y', errors='coerce')
            df_membros.dropna(subset=['Data de Nascimento_dt'], inplace=True)
            df_membros['Mês'] = df_membros['Data de Nascimento_dt'].dt.month
            df_membros['Dia'] = df_membros['Data de Nascimento_dt'].dt.day
            meses_pt = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}
            mes_selecionado = st.selectbox("Escolha o mês para ver a lista de aniversariantes:", options=list(meses_pt.keys()), index=0)
            if mes_selecionado:
                num_mes = meses_pt[mes_selecionado]
                aniversariantes_df = df_membros[df_membros['Mês'] == num_mes].sort_values('Dia')
                st.markdown(f"### Aniversariantes de {mes_selecionado}")
                if aniversariantes_df.empty:
                    st.info("Nenhum aniversariante encontrado para este mês.")
                else:
                    # Prepare o DataFrame para exibição/PDF
                    df_display = aniversariantes_df[['Dia', 'Nome', 'Data de Nascimento']].copy()
                    df_display['Data de Nascimento Completa'] = df_display['Data de Nascimento']
                    df_display.rename(columns={'Nome': 'Nome Completo'}, inplace=True)
                    st.dataframe(df_display[['Dia', 'Nome Completo', 'Data de Nascimento Completa']], use_container_width=True, hide_index=True)
                    st.markdown("---")
                    pdf_data = criar_pdf_aniversariantes(df_display[['Nome Completo', 'Data de Nascimento Completa']], mes_selecionado)
                    st.download_button(label=f"📕 Exportar PDF de {mes_selecionado}", data=pdf_data, file_name=f"aniversariantes_{mes_selecionado.lower()}.pdf", mime="application/pdf")
        else:
            st.info("Não há membros cadastrados para gerar a lista de aniversariantes.")

    with tab5:
        st.header("Gerar Ficha Individual de Membro")
        if "membros" in st.session_state and st.session_state.membros:
            nomes_membros = [m.get("Nome") or m.get("nome", "") for m in st.session_state.membros]
            lista_nomes = ["Selecione um membro..."] + sorted(nomes_membros)
            membro_selecionado_nome = st.selectbox("Selecione um membro para gerar a ficha:", options=lista_nomes, index=0)
            if membro_selecionado_nome and membro_selecionado_nome != "Selecione um membro...":
                membro_dict = next((m for m in st.session_state.membros if (m.get("Nome") or m.get("nome", "")) == membro_selecionado_nome), None)
                if membro_dict:
                    st.markdown("---")
                    st.subheader(f"Ficha de: {membro_dict.get('Nome', membro_dict.get('nome', ''))}")
                    st.markdown("##### 👤 Dados Pessoais")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text("Nome:"); st.info(membro_dict.get("Nome") or membro_dict.get("nome", ""))
                        st.text("Data de Nascimento:"); st.info(membro_dict.get("Data de Nascimento") or membro_dict.get("data_nasc", ""))
                        st.text("Estado Civil:"); st.info(membro_dict.get("Estado Civil") or membro_dict.get("estado_civil", ""))
                    with col2:
                        st.text("CPF:"); st.info(membro_dict.get("CPF") or membro_dict.get("cpf", ""))
                        st.text("Sexo:"); st.info(membro_dict.get("Sexo") or membro_dict.get("sexo", ""))
                        st.text("Profissão:"); st.info(membro_dict.get("Profissão") or membro_dict.get("profissao", ""))
                    st.markdown("---")
                    st.markdown("##### 🏠 Endereço e Contato")
                    col3, col4 = st.columns(2)
                    with col3:
                        st.text("Celular:"); st.info(membro_dict.get("Celular") or membro_dict.get("celular", ""))
                        st.text("Endereço:"); st.info(membro_dict.get("Endereco") or membro_dict.get("endereco", ""))
                        st.text("Cidade:"); st.info(membro_dict.get("Cidade") or membro_dict.get("cidade", ""))
                    with col4:
                        st.text("CEP:"); st.info(membro_dict.get("CEP") or membro_dict.get("cep", ""))
                        st.text("Bairro:"); st.info(membro_dict.get("Bairro") or membro_dict.get("bairro", ""))
                        st.text("UF:"); st.info(membro_dict.get("UF (Endereco)") or membro_dict.get("uf_end", ""))
                    st.markdown("---")
                    if st.button("🖼️ Exportar Ficha como Imagem (.png)"):
                        with st.spinner("Gerando imagem da ficha..."):
                            imagem_data = criar_imagem_ficha(membro_dict)
                            st.download_button(
                                label="Clique para baixar a Imagem",
                                data=imagem_data,
                                file_name=f"ficha_{(membro_dict.get('Nome') or membro_dict.get('nome', '')).replace(' ', '_').lower()}.png",
                                mime="image/png"
                            )
        else:
            st.warning("Não há membros cadastrados para gerar fichas.")
