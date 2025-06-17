import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Tendência Semanal por Coordenador")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

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
    df['Semana'] = df['Data'].dt.isocalendar().week
    df['Ano'] = df['Data'].dt.year

    dias_semana = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_semana'] = df['Data'].dt.day_name().map(dias_semana)

    return df

def minutos_para_horas(minutos):
    try:
        if minutos is None or pd.isna(minutos) or minutos <= 0:
            return 0
        return round(minutos / 60, 2)
    except:
        return 0

# --- Execução ---
df = carregar_dados()
df = analisar_ponto(df)

# --- Filtro por coordenador ---
coordenadores = df['MICROSIGA.COORDENADOR_IMEDIATO'].dropna().unique()
coord_selecionado = st.selectbox("Filtrar por Coordenador:", sorted(coordenadores))

df_coord = df[df['MICROSIGA.COORDENADOR_IMEDIATO'] == coord_selecionado]

# --- Tendência semanal ---
semana_tendencia = (
    df_coord[df_coord['Hora_extra']]
    .groupby(['Ano', 'Semana'])['Minutos_extras']
    .sum()
    .reset_index()
)
semana_tendencia['Horas_extras'] = semana_tendencia['Minutos_extras'].apply(minutos_para_horas)

st.subheader(f"📈 Tendência Semanal de Horas Extras - {coord_selecionado}")
st.dataframe(semana_tendencia[['Ano', 'Semana', 'Horas_extras']], use_container_width=True)
