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

# --- 1) Configuração da página ---
st.set_page_config(layout="wide", page_title="Fichário de Membros PIB Gaibu v4.0")

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
    # Dimensões A5 Paisagem em pixels (300 DPI)
    largura, altura = 2480, 1748
    img = Image.new('RGB', (largura, altura), color='white')
    draw = ImageDraw.Draw(img)

    # Carregar fontes (usando matplotlib para encontrar uma fonte padrão)
    try:
        caminho_fonte = matplotlib.font_manager.findfont('DejaVu Sans')
        fonte_titulo = ImageFont.truetype(caminho_fonte, 100)
        fonte_subtitulo = ImageFont.truetype(caminho_fonte, 70)
        fonte_label = ImageFont.truetype(caminho_fonte, 50)
        fonte_valor = ImageFont.truetype(caminho_fonte, 50)
    except:
        # Fallback para fonte padrão se a do matplotlib não for encontrada
        fonte_titulo = ImageFont.load_default()
        fonte_subtitulo = ImageFont.load_default()
        fonte_label = ImageFont.load_default()
        fonte_valor = ImageFont.load_default()


    # Título
    draw.text((100, 80), "Ficha Individual de Membro", fill='black', font=fonte_titulo)
    draw.line([(100, 200), (largura - 100, 200)], fill='gray', width=5)

    # Layout em duas colunas
    x1, x2 = 120, largura / 2 + 50
    y = 280
    line_height = 80

    # Exibe os dados que não estão vazios
    for chave, valor in membro.items():
        if valor and str(valor).strip():
            # Formatação especial para chaves longas
            label = f"{chave}:"
            if len(label) > 20:
                y += line_height / 2

            # Desenha o Label (chave) e o Valor
            draw.text((x1, y), label, fill='gray', font=fonte_label)
            draw.text((x2, y), str(valor), fill='black', font=fonte_valor)
            y += line_height

            if y > (altura - 200): # Previne overflow de texto, adiciona nova coluna (não implementado)
                # Lógica para nova coluna ou página pode ser adicionada aqui
                pass

    # Salva a imagem em um buffer
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
        # ... (código inalterado)

    with tab2:
        st.header("Lista de Membros")
        # ... (código inalterado)

    with tab3:
        st.header("Buscar, Exportar e Excluir Membros")
        # ... (código inalterado)

    with tab4:
        st.header("Aniversariantes do Mês")
        # ... (código inalterado)
        
    with tab5:
        st.header("Gerar Ficha Individual de Membro")

        if "membros" in st.session_state and st.session_state.membros:
            lista_nomes = ["Selecione um membro..."] + sorted([m.get("Nome", "") for m in st.session_state.membros])
            membro_selecionado_nome = st.selectbox("Selecione um membro para gerar a ficha:", options=lista_nomes)

            if membro_selecionado_nome and membro_selecionado_nome != "Selecione um membro...":
                # Encontra o dicionário completo do membro selecionado
                membro_dict = next((m for m in st.session_state.membros if m.get("Nome") == membro_selecionado_nome), None)
                
                if membro_dict:
                    st.markdown("---")
                    st.subheader(f"Ficha de: {membro_dict['Nome']}")
                    
                    # Exibe os dados em colunas para uma melhor visualização
                    col1, col2 = st.columns(2)
                    
                    # Filtra e divide os itens para exibição
                    itens_preenchidos = {k: v for k, v in membro_dict.items() if v and str(v).strip()}
                    itens_metade = len(itens_preenchidos) // 2
                    
                    itens_col1 = dict(list(itens_preenchidos.items())[:itens_metade])
                    itens_col2 = dict(list(itens_preenchidos.items())[itens_metade:])

                    with col1:
                        for chave, valor in itens_col1.items():
                            st.text(f"{chave}:")
                            st.info(valor)
                    
                    with col2:
                        for chave, valor in itens_col2.items():
                            st.text(f"{chave}:")
                            st.info(valor)

                    st.markdown("---")
                    
                    # Botão para gerar e baixar a imagem
                    if st.button("🖼️ Exportar Ficha como Imagem (.png)"):
                        with st.spinner("Gerando imagem da ficha..."):
                            imagem_data = criar_imagem_ficha(membro_dict)
                            st.download_button(
                                label="Clique para baixar a Imagem",
                                data=imagem_data,
                                file_name=f"ficha_{membro_dict['Nome'].replace(' ', '_').lower()}.png",
                                mime="image/png"
                            )
        else:
            st.warning("Não há membros cadastrados para gerar fichas.")
