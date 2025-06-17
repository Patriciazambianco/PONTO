import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_hms(minutos):
    try:
        if minutos is None or pd.isna(minutos) or minutos <= 0:
            return "00:00:00"
        minutos_int = int(round(minutos))
        h = minutos_int // 60
        m = minutos_int % 60
        return f"{h:02d}:{m:02d}:00"
    except:
        return "00:00:00"

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
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
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

meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses_disponiveis)

df_mes = df[df['Mes_Ano'] == mes_selecionado]

# Ranking horas extras
ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index(name='Total_minutos_extras')
)

ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutos_para_hms)
ranking_horas = ranking_horas.sort_values(by='Total_minutos_extras', ascending=False)

# Ranking dias fora do turno
ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
)
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias_fora_turno', ascending=False)

col1, col2 = st.columns(2)

with col1:
    st.subheader(f"⏰ Ranking - Horas Extras ({mes_selecionado})")
    selecionado_horas = st.selectbox("Selecione o funcionário (Horas Extras):", ranking_horas['Nome'].tolist())
    st.dataframe(
        ranking_horas.rename(columns={'Nome': 'Funcionário', 'Horas_fmt': 'Horas Extras'})[['Funcionário', 'Horas_fmt']],
        use_container_width=True
    )

with col2:
    st.subheader(f"🚨 Ranking - Dias Fora do Turno ({mes_selecionado})")
    selecionado_fora = st.selectbox("Selecione o funcionário (Fora do Turno):", ranking_fora_turno['Nome'].tolist())
    st.dataframe(
        ranking_fora_turno.rename(columns={'Nome': 'Funcionário'})[['Funcionário', 'Dias_fora_turno']],
        use_container_width=True
    )

# Detalhamento funcionário horas extras
st.markdown("---")
st.subheader("Detalhamento do Funcionário Selecionado")

if selecionado_horas:
    st.markdown(f"**Funcionário (Horas Extras):** {selecionado_horas}")
    detalhes_horas = df_mes[(df_mes['Nome'] == selecionado_horas) & (df_mes['Hora_extra'])]
    st.dataframe(
        detalhes_horas[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Minutos_extras']].rename(
            columns={
                'Data_fmt': 'Data',
                'Entrada_fmt': 'Entrada',
                'Saida_fmt': 'Saída',
                'Turnos.ENTRADA': 'Turno Entrada',
                'Turnos.SAIDA': 'Turno Saída',
                'Minutos_extras': 'Minutos Extras'
            }
        ),
        use_container_width=True
    )

# Detalhamento funcionário fora do turno
if selecionado_fora:
    st.markdown(f"**Funcionário (Fora do Turno):** {selecionado_fora}")
    detalhes_fora = df_mes[(df_mes['Nome'] == selecionado_fora) & (df_mes['Entrada_fora_turno'])]
    st.dataframe(
        detalhes_fora[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA']].rename(
            columns={
                'Data_fmt': 'Data',
                'Entrada_fmt': 'Entrada',
                'Saida_fmt': 'Saída',
                'Turnos.ENTRADA': 'Turno Entrada',
                'Turnos.SAIDA': 'Turno Saída',
            }
        ),
        use_container_width=True
    )
