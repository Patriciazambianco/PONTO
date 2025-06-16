import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("Horas Extras e Fora do Turno por Mês")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

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
        dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

def minutes_to_hms(minutes):
    if pd.isna(minutes) or minutes is None or minutes <= 0:
        return "00:00:00"
    h = int(minutes) // 60
    m = int(minutes) % 60
    return f"{h:02d}:{m:02d}:00"

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
        if (row['Minutos_trabalhados'] is not None and
            row['Minutos_turno_saida'] is not None and
            row['Minutos_turno_entrada'] is not None)
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15

    df['AnoMes'] = df['Data'].dt.to_period('M').astype(str)

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m/%Y')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

df = carregar_dados()
df = analisar_ponto(df)

# Filtro por mês
meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
mes_selecionado = st.selectbox("Selecione o mês:", meses_disponiveis)

df_mes = df[df['AnoMes'] == mes_selecionado]

# Ranking horas extras por nome no mês
ranking_horas = df_mes[df_mes['Hora_extra']].groupby('Nome').agg({'Minutos_extras':'sum'}).reset_index()
ranking_horas['Horas Extras'] = ranking_horas['Minutos_extras'].apply(minutes_to_hms)
ranking_horas = ranking_horas.sort_values(by='Minutos_extras', ascending=False).reset_index(drop=True)

# Ranking fora do turno no mês
ranking_fora_turno = df_mes[df_mes['Entrada_fora_turno']].groupby('Nome').size().reset_index(name='Dias Fora do Turno')
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias Fora do Turno', ascending=False).reset_index(drop=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"🚀 Ranking - Total de Horas Extras em {mes_selecionado}")
    st.dataframe(ranking_horas[['Nome', 'Horas Extras']], use_container_width=True)

with col2:
    st.subheader(f"⏰ Ranking - Dias Fora do Turno em {mes_selecionado}")
    st.dataframe(ranking_fora_turno, use_container_width=True)

# Mostrar datas e horários das infrações ao clicar no nome (horas extras)
st.markdown("---")
st.subheader(f"🔎 Detalhamento das Infrações - {mes_selecionado}")

selected_horas = st.selectbox("Selecione um funcionário para ver as horas extras:", ranking_horas['Nome'].tolist() if not ranking_horas.empty else [])
selected_fora = st.selectbox("Selecione um funcionário para ver os dias fora do turno:", ranking_fora_turno['Nome'].tolist() if not ranking_fora_turno.empty else [])

if selected_horas:
    df_func_horas = df_mes[(df_mes['Nome'] == selected_horas) & (df_mes['Hora_extra'])]
    df_func_horas = df_func_horas[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Minutos_extras']]
    df_func_horas['Horas Extras'] = df_func_horas['Minutos_extras'].apply(minutes_to_hms)
    st.write(f"🕒 Horas Extras de {selected_horas}:")
    st.dataframe(df_func_horas[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas Extras']], use_container_width=True)

if selected_fora:
    df_func_fora = df_mes[(df_mes['Nome'] == selected_fora) & (df_mes['Entrada_fora_turno'])]
    df_func_fora = df_func_fora[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA']]
    df_func_fora['Turno Entrada'] = df_func_fora['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df_func_fora['Turno Saída'] = df_func_fora['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    st.write(f"⏰ Dias Fora do Turno de {selected_fora}:")
    st.dataframe(df_func_fora[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turno Entrada', 'Turno Saída']], use_container_width=True)
