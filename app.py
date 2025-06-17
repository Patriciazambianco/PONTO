import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_hms(minutos):
    if pd.isna(minutos) or minutos <= 0:
        return "00:00:00"
    h = minutos // 60
    m = minutos % 60
    return f"{int(h):02d}:{int(m):02d}:00"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    df = pd.read_excel(BytesIO(response.content))

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time
    return df

def diff_minutes(t1, t2):
    try:
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

@st.cache_data
def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    df['Entrada_fora_turno'] = df.apply(
        lambda row: (
            row['Minutos_entrada'] is not None and
            row['Minutos_turno_entrada'] is not None and
            abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        ), axis=1)

    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1)

    df['Minutos_extras'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
        if row['Minutos_trabalhados'] and row['Minutos_turno_saida'] and row['Minutos_turno_entrada'] else 0,
        axis=1)

    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)

    return df

# Carregar e processar
raw_df = carregar_dados()
df = analisar_ponto(raw_df.copy())

meses = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses)
df_mes = df[df['Mes_Ano'] == mes_selecionado]

# Ranking Horas Extras
df_horas = df_mes[df_mes['Hora_extra']]
ranking_horas = df_horas.groupby('Nome')['Minutos_extras'].sum().reset_index()
ranking_horas = ranking_horas.sort_values(by='Minutos_extras', ascending=False).head(20)
ranking_horas['Horas_fmt'] = ranking_horas['Minutos_extras'].apply(minutos_para_hms)

# Ranking Fora do Turno
df_fora = df_mes[df_mes['Entrada_fora_turno']]
ranking_fora = df_fora.groupby('Nome').size().reset_index(name='Dias_fora_turno')
ranking_fora = ranking_fora.sort_values(by='Dias_fora_turno', ascending=False).head(20)

# Interface com heatmap
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔥 Top 20 Horas Extras (com mapa de calor)")
    st.dataframe(
        ranking_horas.style.background_gradient(cmap='Reds', subset=['Minutos_extras']).format({
            'Minutos_extras': '{:.0f}',
            'Horas_fmt': '{}'
        }),
        use_container_width=True
    )

with col2:
    st.subheader("🚨 Top 20 Fora do Turno (com mapa de calor)")
    st.dataframe(
        ranking_fora.style.background_gradient(cmap='Oranges', subset=['Dias_fora_turno']),
        use_container_width=True
    )
