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

# --- A) Parâmetros de Login Google (lendo dos Segredos) ---
try:
    GOOGLE_CLIENT_ID = st.secrets["google_oauth"]["client_id"]
    GOOGLE_CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
    GOOGLE_REDIRECT_URI = "https://pibgaibu.streamlit.app"
    EMAILS_PERMITIDOS = {
        "antonio.esn01@gmail.com",
        "neto1999.legal@gmail.com",
        "adrielsoliveira1907@gmail.com"
    }
    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token"
    )
except (KeyError, FileNotFoundError):
    st.error("As credenciais de login (Google OAuth) não foram encontradas nos Segredos do Streamlit. Por favor, configure os segredos.")
    st.stop()

# Inicializa o estado da sessão
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, col_login, _ = st.columns([0.5, 2, 0.5])
    with col_login:
        st.markdown("<h1 style='text-align: center;'>Fichário de Membros</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: grey;'>PIB Gaibu</h3>", unsafe_allow_html=True)
        st.markdown("---")
        token = oauth2.authorize_button(
            "Entrar com Google",
            key="google_login",
            redirect_uri=GOOGLE_REDIRECT_URI,
            scope="openid email profile"
        )
        st.json(token)  # <-- LINHA DE DEPURAÇÃO ADICIONADA AQUI

        if token:
            try:
                id_token = token.get("id_token")
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
                    st.error("Resposta de autenticação inválida recebida do Google.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o login: {e}")

else:
    # Seu restante do app aqui (carregamento de dados, abas, etc.)
    st.success(f"Bem-vindo(a), {st.session_state.get('username', '')}!")
    if st.button("Sair"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()
    # ... restante das abas do app ...
