import streamlit as st
from streamlit_oauth import OAuth2Component
import jwt

st.set_page_config(layout="wide", page_title="Teste de Login")

# Verifica se os segredos estão configurados
if "google_oauth" not in st.secrets or "google_sheets" not in st.secrets:
    st.error("Os segredos do Google (google_oauth e google_sheets) não foram encontrados. Por favor, configure-os em 'Settings' -> 'Secrets'.")
    st.stop()

# Configuração do OAuth
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

st.title("Diagnóstico de Login do Google")
st.info("Clique no botão abaixo para tentar a autenticação.")

# Botão de autorização
token = oauth2.authorize_button(
    "Entrar com Google",
    redirect_uri=GOOGLE_REDIRECT_URI,
    scope="openid email profile"
)

# --- LINHA DE DEPURAÇÃO CRÍTICA ---
st.write("--- Resposta Bruta Recebida do Servidor do Google ---")
st.json(token) # Imprime a resposta completa na tela
st.write("-----------------------------------------------------")

if token:
    id_token = token.get("id_token")
    if id_token:
        st.success("SUCESSO! O id_token foi recebido corretamente.")
        try:
            user_info = jwt.decode(id_token.encode(), options={"verify_signature": False})
            st.write("Informações do usuário decodificadas:")
            st.json(user_info)
        except Exception as e:
            st.error(f"Erro ao decodificar o token: {e}")
    else:
        st.error("FALHA: O id_token não foi encontrado na resposta do Google. Verifique a resposta bruta acima para uma mensagem de erro (ex: 'invalid_client', 'invalid_grant').")
