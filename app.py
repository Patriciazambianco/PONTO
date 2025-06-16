import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto – Ranking Mensal de Horas Extras e Fora do Turno")

# URL do Excel
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
    if minutes <= 0:
        return "00:00:00"
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}:00"

@st.cache_data
def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    # Fora do turno = diferença maior que 60 minutos na entrada
    df['Entrada_fora_turno'] = df.apply(
        lambda row: (
            row['Minutos_entrada'] is not None and
            row['Minutos_turno_entrada'] is not None and
            abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        ),
        axis=1
    )

    # Minutos trabalhados
    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )

    # Minutos extras = minutos trabalhados menos turno (positivo ou zero)
    df['Minutos_extras'] = df.apply(
        lambda row: max(
            (row['Minutos_trabalhados'] or 0) - 
            ((row['Minutos_turno_saida'] or 0) - (row['Minutos_turno_entrada'] or 0)),
            0
        ),
        axis=1
    )

    # Considera hora extra se > 15 minutos
    df['Hora_extra'] = df['Minutos_extras'] > 15

    # Ano e Mês para filtro
    df['AnoMes'] = df['Data'].dt.to_period('M').astype(str)

    return df

# Rodando tudo
df = carregar_dados()
df = analisar_ponto(df)

# Filtro de mês
meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
mes_selecionado = st.selectbox("Selecione o mês:", meses_disponiveis)

df_mes = df[df['AnoMes'] == mes_selecionado]

# Ranking Horas Extras por funcionário
ranking_horas = df_mes[df_mes['Hora_extra']].groupby('Nome')['Minutos_extras'].sum().reset_index()
ranking_horas['Horas Extras'] = ranking_horas['Minutos_extras'].apply(minutes_to_hms)
ranking_horas = ranking_horas.sort_values(by='Minutos_extras', ascending=False)

# Ranking Fora do turno por funcionário (conta dias únicos)
ranking_fora_turno = df_mes[df_mes['Entrada_fora_turno']].groupby('Nome')['Data'].nunique().reset_index()
ranking_fora_turno = ranking_fora_turno.rename(columns={'Data': 'Dias Fora do Turno'})
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias Fora do Turno', ascending=False)

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"🚀 Ranking - Total de Horas Extras ({mes_selecionado})")
    selected_hora = st.radio("Clique no nome para detalhes:", ranking_horas['Nome'].tolist(), key="horas")
    st.dataframe(ranking_horas[['Nome', 'Horas Extras']].set_index('Nome'))

with col2:
    st.subheader(f"⏰ Ranking - Dias Fora do Turno ({mes_selecionado})")
    selected_fora = st.radio("Clique no nome para detalhes:", ranking_fora_turno['Nome'].tolist(), key="fora")
    st.dataframe(ranking_fora_turno.set_index('Nome'))

# Mostrar detalhes quando clicar no nome em horas extras
if selected_hora:
    st.markdown(f"### 🔍 Detalhes de Horas Extras de {selected_hora}")
    df_sel = df_mes[(df_mes['Nome'] == selected_hora) & (df_mes['Hora_extra'])]
    df_sel = df_sel[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Minutos_extras']]
    df_sel['Horas Extras'] = df_sel['Minutos_extras'].apply(minutes_to_hms)
    df_sel['Data'] = df_sel['Data'].dt.strftime('%d/%m/%Y')
    df_sel['Entrada 1'] = df_sel['Entrada 1'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    df_sel['Saída 1'] = df_sel['Saída 1'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    df_sel['Turnos.ENTRADA'] = df_sel['Turnos.ENTRADA'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    df_sel['Turnos.SAIDA'] = df_sel['Turnos.SAIDA'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    st.dataframe(df_sel.drop(columns=['Minutos_extras']))

# Mostrar detalhes quando clicar no nome em fora do turno
if selected_fora:
    st.markdown(f"### 🔍 Detalhes de Dias Fora do Turno de {selected_fora}")
    df_sel = df_mes[(df_mes['Nome'] == selected_fora) & (df_mes['Entrada_fora_turno'])]
    df_sel = df_sel[['Data', 'Entrada 1', 'Turnos.ENTRADA']]
    df_sel['Data'] = df_sel['Data'].dt.strftime('%d/%m/%Y')
    df_sel['Entrada 1'] = df_sel['Entrada 1'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    df_sel['Turnos.ENTRADA'] = df_sel['Turnos.ENTRADA'].apply(lambda t: t.strftime('%H:%M') if pd.notnull(t) else '')
    st.dataframe(df_sel)

