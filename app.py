import streamlit as st
import pandas as pd
import requests
from io import BytesIO

st.title("Resumo Básico: Horas Extras e Entrada Fora da Jornada")

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
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return 0

def minutos_para_horas(minutos):
    if minutos is None or pd.isna(minutos) or minutos <= 0:
        return "0:00"
    h = int(minutos) // 60
    m = int(minutos) % 60
    return f"{h}:{m:02d}"

@st.cache_data
def preparar_dados(df):
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)

    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour*60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour*60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour*60 + t.minute if pd.notnull(t) else None)

    df['Entrada_fora_turno'] = df.apply(
        lambda r: abs(r['Minutos_entrada'] - r['Minutos_turno_entrada']) > 60
        if (r['Minutos_entrada'] is not None and r['Minutos_turno_entrada'] is not None) else False,
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(
        lambda r: diff_minutes(r['Entrada 1'], r['Saída 1']) if r['Entrada 1'] and r['Saída 1'] else 0,
        axis=1
    )

    df['Minutos_esperados'] = df.apply(
        lambda r: r['Minutos_turno_saida'] - r['Minutos_turno_entrada']
        if (r['Minutos_turno_saida'] is not None and r['Minutos_turno_entrada'] is not None) else 0,
        axis=1
    )

    df['Minutos_extras'] = df['Minutos_trabalhados'] - df['Minutos_esperados']
    df['Minutos_extras'] = df['Minutos_extras'].apply(lambda x: x if x > 15 else 0)

    return df

df = carregar_dados()
df = preparar_dados(df)

# Ranking mensal de horas extras
ranking_horas = (
    df.groupby(['Mes_Ano', 'Nome'])['Minutos_extras']
    .sum()
    .reset_index()
)

ranking_horas = ranking_horas[ranking_horas['Minutos_extras'] > 0]
ranking_horas['Horas_Extras'] = ranking_horas['Minutos_extras'].apply(minutos_para_horas)

# Ranking mensal de entradas fora do turno
ranking_fora_turno = (
    df[df['Entrada_fora_turno']]
    .groupby(['Mes_Ano', 'Nome'])
    .size()
    .reset_index(name='Dias_fora_turno')
)

st.header("📅 Escolha o mês")
meses = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Mês para exibir os rankings", meses)

st.subheader(f"🏆 Ranking de Horas Extras - {mes_selecionado}")
horas_mes = ranking_horas[ranking_horas['Mes_Ano'] == mes_selecionado].sort_values(by='Minutos_extras', ascending=False)
if not horas_mes.empty:
    st.dataframe(horas_mes[['Nome', 'Horas_Extras']].rename(columns={'Nome': 'Funcionário', 'Horas_Extras': 'Horas Extras'}))
else:
    st.write("Nenhuma hora extra registrada neste mês.")

st.subheader(f"⚠️ Ranking de Entradas Fora do Turno - {mes_selecionado}")
fora_turno_mes = ranking_fora_turno[ranking_fora_turno['Mes_Ano'] == mes_selecionado].sort_values(by='Dias_fora_turno', ascending=False)
if not fora_turno_mes.empty:
    st.dataframe(fora_turno_mes[['Nome', 'Dias_fora_turno']].rename(columns={'Nome': 'Funcionário', 'Dias_fora_turno': 'Dias Fora do Turno'}))
else:
    st.write("Nenhuma entrada fora do turno registrada neste mês.")
