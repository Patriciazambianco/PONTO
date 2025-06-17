import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_hms(minutos):
    if pd.isna(minutos) or minutos <= 0:
        return "00:00"
    h = int(minutos // 60)
    m = int(minutos % 60)
    return f"{h:02d}:{m:02d}"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

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
        ),
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )

    df['Minutos_extras'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
        if row['Minutos_trabalhados'] is not None and row['Minutos_turno_saida'] is not None and row['Minutos_turno_entrada'] is not None
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

df = carregar_dados()
df = analisar_ponto(df)

st.markdown("### 📅 Ranking Consolidado por Mês")

# Ranking geral por mês
ranking_mes_horas = (
    df[df['Hora_extra']]
    .groupby(['Mes_Ano', 'Nome'])['Minutos_extras']
    .sum()
    .reset_index()
)
ranking_mes_horas['Horas_fmt'] = ranking_mes_horas['Minutos_extras'].apply(minutos_para_hms)

ranking_mes_turno = (
    df[df['Entrada_fora_turno']]
    .groupby(['Mes_Ano', 'Nome'])
    .size()
    .reset_index(name='Dias_fora_turno')
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### ⏱️ Horas Extras por Mês")
    st.dataframe(
        ranking_mes_horas.sort_values(by=['Mes_Ano', 'Minutos_extras'], ascending=[False, False]),
        use_container_width=True
    )

with col2:
    st.markdown("#### 🚨 Fora do Turno por Mês")
    st.dataframe(
        ranking_mes_turno.sort_values(by=['Mes_Ano', 'Dias_fora_turno'], ascending=[False, False]),
        use_container_width=True
    )
