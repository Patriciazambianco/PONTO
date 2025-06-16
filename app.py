import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta, time

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def to_time_safe(x):
    """Converte vários formatos para time, retorna None se falhar."""
    if pd.isna(x):
        return None
    if isinstance(x, pd.Timestamp):
        return x.time()
    if isinstance(x, str):
        for fmt in ("%H:%M:%S", "%H:%M", "%H.%M", "%H-%M"):
            try:
                return datetime.strptime(x, fmt).time()
            except:
                continue
    return None

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)

    df['Entrada 1'] = df['Entrada 1'].apply(to_time_safe)
    df['Saída 1'] = df['Saída 1'].apply(to_time_safe)
    df['Turnos.ENTRADA'] = df['Turnos.ENTRADA'].apply(to_time_safe)
    df['Turnos.SAIDA'] = df['Turnos.SAIDA'].apply(to_time_safe)

    return df

def time_to_minutes(t):
    if t is None:
        return None
    return t.hour * 60 + t.minute + t.second / 60

def analyze_ponto(df):
    # Converter horários para minutos para facilitar cálculo
    df['entrada_min'] = df['Entrada 1'].apply(time_to_minutes)
    df['saida_min'] = df['Saída 1'].apply(time_to_minutes)
    df['turno_entrada_min'] = df['Turnos.ENTRADA'].apply(time_to_minutes)
    df['turno_saida_min'] = df['Turnos.SAIDA'].apply(time_to_minutes)

    # Definições:
    # Fora do turno = entrada mais de 60 min depois do turno oficial
    df['fora_turno'] = df['entrada_min'] > (df['turno_entrada_min'] + 60)

    # Hora extra = saída mais de 15 minutos depois do turno oficial de saída
    df['hora_extra'] = df['saida_min'] > (df['turno_saida_min'] + 15)

    return df

def ranking_reincidentes(df):
    # Filtra quem está fora do turno ou com hora extra
    fora = df[df['fora_turno']]
    extra = df[df['hora_extra']]

    # Conta reincidência por funcionário
    rank_fora = fora.groupby('Nome').size().reset_index(name='Dias Fora do Turno').sort_values(by='Dias Fora do Turno', ascending=False)
    rank_extra = extra.groupby('Nome').size().reset_index(name='Dias Hora Extra').sort_values(by='Dias Hora Extra', ascending=False)

    return rank_fora, rank_extra

# --- Main ---

st.title("Análise de Ponto - Fora do Turno e Hora Extra")

df = carregar_dados()

df = analyze_ponto(df)

st.subheader("Tabela com análises")
st.dataframe(df[['Nome', 'Data', 'Entrada 1', 'Turnos.ENTRADA', 'Saída 1', 'Turnos.SAIDA', 'fora_turno', 'hora_extra']])

rank_fora, rank_extra = ranking_reincidentes(df)

st.subheader("Ranking - Funcionários que mais chegaram Fora do Turno (>1 hora depois)")
st.table(rank_fora)

st.subheader("Ranking - Funcionários que mais fizeram Hora Extra (>15 minutos após saída do turno)")
st.table(rank_extra)
