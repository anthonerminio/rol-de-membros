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
st.set_page_config(layout="wide", page_title="Fichário de Membros v4.0")

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
    img = Image.new('RGB', (largura, altura), color=(240, 242, 246))
    draw = ImageDraw.Draw(img)

    try:
        caminho_fonte = matplotlib.font_manager.findfont('DejaVu Sans')
        fonte_titulo = ImageFont.truetype(caminho_fonte, 90)
        fonte_sub = ImageFont.truetype(caminho_fonte, 60)
        fonte_label = ImageFont.truetype(caminho_fonte, 45)
        fonte_valor = ImageFont.truetype(caminho_fonte, 45)
    except:
        fonte_titulo, fonte_sub, fonte_label, fonte_valor = [ImageFont.load_default()]*4

    # Cabeçalho
    draw.rectangle([(0, 0), (largura, 220)], fill='#0E1117')
    draw.text((100, 80), "Ficha Individual de Membro - PIB Gaibu", fill='white', font=fonte_titulo)

    y = 280
    x_col1, x_col2 = 120, largura / 2

    def draw_field(x, y, label, value, label_font, value_font):
        if value and str(value).strip():
            draw.text((x, y), label, fill=(100, 116, 139), font=label_font)
            draw.text((x, y + 50), str(value), fill='black', font=value_font)
            return 120 # Altura do campo desenhado
        return 0

    # DADOS PESSOAIS
    draw.text((x_col1, y), "👤 Dados Pessoais", fill='black', font=fonte_sub)
    y += 100
    y += draw_field(x_col1, y, "Nome Completo", membro.get("Nome"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "CPF", membro.get("CPF"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Data de Nascimento", membro.get("Data de Nascimento"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Sexo", membro.get("Sexo"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Estado Civil", membro.get("Estado Civil"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Profissão", membro.get("Profissão"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Celular", membro.get("Celular"), fonte_label, fonte_valor)
    y += draw_field(x_col1, y, "Grau de Instrução", membro.get("Grau de Instrução"), fonte_label, fonte_valor)

    # FILIAÇÃO
    y_col2 = 280
    draw.text((x_col2, y_col2), "👨‍👩‍👧 Filiação e Origem", fill='black', font=fonte_sub)
    y_col2 += 100
    y_col2 += draw_field(x_col2, y_col2, "Nome do Pai", membro.get("Nome do Pai"), fonte_label, fonte_valor)
    y_col2 += draw_field(x_col2, y_col2, "Nome da Mãe", membro.get("Nome da Mae"), fonte_label, fonte_valor)
    y_col2 += draw_field(x_col2, y_col2, "Nome do(a) Cônjuge", membro.get("Nome do(a) Cônjuge"), fonte_label, fonte_valor)
    y_col2 += draw_field(x_col2, y_col2, "Nacionalidade", membro.get("Nacionalidade"), fonte_label, fonte_valor)
    y_col2 += draw_field(x_col2, y_col2, "Naturalidade", membro.get("Naturalidade"), fonte_label, fonte_valor)
    
    # DADOS ECLESIÁSTICOS
    y = max(y, y_col2) + 50
    draw.line([(100, y - 20), (largura - 100, y - 20)], fill='gray', width=2)
    draw.text((x_col1, y), "⛪ Dados Eclesiásticos", fill='black', font=fonte_sub)
    y += 100
    
    col_ec_x = [x_col1, x_col1 + (largura/4), x_col1 + 2*(largura/4), x_col1 + 3*(largura/4)]
    draw_field(col_ec_x[0], y, "Forma de Admissão", membro.get("Forma de Admissao"), fonte_label, fonte_valor)
    draw_field(col_ec_x[1], y, "Data de Admissão", membro.get("Data de Admissao"), fonte_label, fonte_valor)
    draw_field(col_ec_x[2], y, "Data de Conversão", membro.get("Data de Conversao"), fonte_label, fonte_valor)
    draw_field(col_ec_x[3], y, "Status", membro.get("Status"), fonte_label, fonte_valor)

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


# --- O restante do código (funções de dados, init_state, etc.) permanece o mesmo ---
# ... (Cole aqui o restante do seu código da versão anterior) ...
