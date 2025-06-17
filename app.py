import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto")

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

    # Formatação para exibição
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Turno_fmt'] = df['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '') + " - " + df['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

def minutes_to_hms(minutos):
    try:
        if minutos is None or pd.isna(minutos) or minutos <= 0:
            return "00:00:00"
        minutos_int = int(round(minutos))
        h = minutos_int // 60
        m = minutos_int % 60
        return f"{h:02d}:{m:02d}:00"
    except Exception:
        return "00:00:00"

# Carregar e processar os dados
df = carregar_dados()
df = analisar_ponto(df)

# --- ABA TABELA RESUMO ---
st.markdown("## 📆 Tabela Resumo por Funcionário")
meses = ['2024-03', '2024-04', '2024-05', '2024-06']
resumo = df[df['Mes_Ano'].isin(meses)].copy()
resumo['Horas_fmt'] = resumo['Minutos_extras'].apply(minutes_to_hms)

# Agregação
tabela = resumo.groupby('Nome').agg({
    'Minutos_extras': 'sum',
    'Turno_fmt': 'first'
}).reset_index()
tabela['Total_Horas_Extras'] = tabela['Minutos_extras'].apply(minutes_to_hms)

for mes in meses:
    mes_df = resumo[resumo['Mes_Ano'] == mes].groupby('Nome')['Minutos_extras'].sum().apply(minutes_to_hms)
    tabela[mes] = tabela['Nome'].map(mes_df)

# Deslocamentos
deslocamentos = resumo[resumo['Entrada_fora_turno']].groupby('Nome')['Data_fmt'].apply(list).reset_index(name='Deslocamentos')
tabela = tabela.merge(deslocamentos, on='Nome', how='left')

st.dataframe(tabela[['Nome', 'Turno_fmt', 'Total_Horas_Extras'] + meses + ['Deslocamentos']], use_container_width=True)

# Botão de download
st.download_button(
    label="📥 Baixar Excel",
    data=tabela.to_csv(index=False).encode('utf-8'),
    file_name="resumo_ponto.csv",
    mime='text/csv'
)
