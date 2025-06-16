import streamlit as st
import pandas as pd
import requests
from io import BytesIO

URL = "URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"
"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()  # garante erro se falhar o download
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Ajusta tipos de data e hora
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)

    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time

    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time

    return df

df = carregar_dados()

st.title("Análise de Ponto")

st.write("Dados carregados com sucesso!")
st.dataframe(df)

# Aqui você pode continuar seu código para análises, gráficos, filtros, etc.

