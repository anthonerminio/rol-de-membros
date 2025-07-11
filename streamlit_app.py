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
    img = Image.new('RGB', (255, 255, 255), color='white')
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
    draw.rectangle([(0, 0), (largura, 180)], fill=(14, 17, 23)) # Cor escura do tema do Streamlit
    draw.text((80, 50), "Ficha Individual de Membro", fill='white', font=fonte_titulo)
    draw.text((largura - 450, 70), "PIB Gaibu", fill='gray', font=fonte_sub)

    # Função auxiliar para desenhar campos
    def draw_field(x, y, label, value):
        if value and str(value).strip():
            draw.text((x, y), label, fill=(100, 116, 139), font=fonte_label) # Cor cinza para o label
            draw.text((x + 450, y), str(value), fill='black', font=fonte_valor)
            return 85 # Altura do campo
        return 0

    y_pos = 250
    x_pos1, x_pos2 = 100, largura / 2 + 50

    # Dados Pessoais
    draw.text((x_pos1, y_pos), "👤 Dados Pessoais", fill='black', font=fonte_sub)
    y_pos += 100
    y_pos += draw_field(x_pos1, y_pos, "Nome:", membro.get("Nome"))
    y_pos += draw_field(x_pos1, y_pos, "CPF:", membro.get("CPF"))
    y_pos += draw_field(x_pos1, y_pos, "Data de Nascimento:", membro.get("Data de Nascimento"))
    y_pos += draw_field(x_pos1, y_pos, "Sexo:", membro.get("Sexo"))
    y_pos += draw_field(x_pos1, y_pos, "Estado Civil:", membro.get("Estado Civil"))
    y_pos += draw_field(x_pos1, y_pos, "Profissão:", membro.get("Profissão"))

    # Contato e Origem
    y_pos2 = 250
    draw.text((x_pos2, y_pos2), "📞 Contato e Origem", fill='black', font=fonte_sub)
    y_pos2 += 100
    y_pos2 += draw_field(x_pos2, y_pos2, "Celular:", membro.get("Celular"))
    y_pos2 += draw_field(x_pos2, y_pos2, "Nacionalidade:", membro.get("Nacionalidade"))
    y_pos2 += draw_field(x_pos2, y_pos2, "Naturalidade:", membro.get("Naturalidade"))
    y_pos2 += draw_field(x_pos2, y_pos2, "UF (Naturalidade):", membro.get("UF (Naturalidade)"))

    # Endereço
    y_pos = max(y_pos, y_pos2) + 50
    draw.line([(100, y), (largura - 100, y)], fill='lightgray', width=3)
    y_pos += 30
    draw.text((x_pos1, y_pos), "🏠 Endereço", fill='black', font=fonte_sub)
    y_pos += 100
    y_pos += draw_field(x_pos1, y_pos, "CEP:", membro.get("CEP"))
    y_pos += draw_field(x_pos1, y_pos, "Endereço:", membro.get("Endereco"))
    y_pos += draw_field(x_pos1, y_pos, "Bairro:", membro.get("Bairro"))
    y_pos += draw_field(x_pos1, y_pos, "Cidade:", membro.get("Cidade"))
    y_pos += draw_field(x_pos1, y_pos, "UF (Endereço):", membro.get("UF (Endereco)"))
    
    # ... (outras seções podem ser adicionadas de forma similar)

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


# --- O restante do código (funções de dados, init_state, etc.) ---
# ...
