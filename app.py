import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

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

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

df = carregar_dados()
df = analisar_ponto(df)

meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses_disponiveis)

df_mes = df[df['Mes_Ano'] == mes_selecionado]

# Ranking Horas Extras - top 20
ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index(name='Total_minutos_extras')
)
ranking_horas['Horas_extras'] = ranking_horas['Total_minutos_extras'] / 60
ranking_horas = ranking_horas.sort_values(by='Horas_extras', ascending=False).head(20)

# Ranking Fora do Turno - top 20
ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
)
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias_fora_turno', ascending=False).head(20)

# Layout lado a lado com 4 colunas
col1, col2, col3, col4 = st.columns([2, 3, 2, 3])

with col1:
    st.subheader(f"⏰ Top 20 Horas Extras ({mes_selecionado})")
    nome_selecionado_horas = st.selectbox("Funcionário (Horas Extras):", ranking_horas['Nome'].tolist(), key='sel_horas')
    st.dataframe(ranking_horas.rename(columns={'Nome': 'Funcionário', 'Horas_extras': 'Horas Extras (h)'}), use_container_width=True)

with col2:
    st.subheader(f"Detalhes Horas Extras - {nome_selecionado_horas}")
    df_det_horas = df_mes[(df_mes['Nome'] == nome_selecionado_horas) & (df_mes['Hora_extra'])]
    df_det_horas_display = df_det_horas[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Minutos_extras']]
    df_det_horas_display['Horas_extras'] = df_det_horas_display['Minutos_extras'] / 60
    df_det_horas_display = df_det_horas_display.rename(columns={
        'Data_fmt': 'Data',
        'Entrada_fmt': 'Entrada',
        'Saida_fmt': 'Saída',
        'Turnos.ENTRADA': 'Turno Entrada',
        'Turnos.SAIDA': 'Turno Saída',
        'Horas_extras': 'Horas Extras (h)'
    })
    st.dataframe(df_det_horas_display[['Data', 'Entrada', 'Saída', 'Turno Entrada', 'Turno Saída', 'Horas Extras (h)']], use_container_width=True)

with col3:
    st.subheader(f"🚨 Top 20 Fora do Turno ({mes_selecionado})")
    nome_selecionado_fora = st.selectbox("Funcionário (Fora do Turno):", ranking_fora_turno['Nome'].tolist(), key='sel_fora')
    st.dataframe(ranking_fora_turno.rename(columns={'Nome': 'Funcionário', 'Dias_fora_turno': 'Dias Fora do Turno'}), use_container_width=True)

with col4:
    st.subheader(f"Detalhes Fora do Turno - {nome_selecionado_fora}")
    df_det_fora = df_mes[(df_mes['Nome'] == nome_selecionado_fora) & (df_mes['Entrada_fora_turno'])]
    df_det_fora_display = df_det_fora[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA']]
    df_det_fora_display = df_det_fora_display.rename(columns={
        'Data_fmt': 'Data',
        'Entrada_fmt': 'Entrada',
        'Saida_fmt': 'Saída',
        'Turnos.ENTRADA': 'Turno Entrada',
        'Turnos.SAIDA': 'Turno Saída'
    })
    st.dataframe(df_det_fora_display[['Data', 'Entrada', 'Saída', 'Turno Entrada', 'Turno Saída']], use_container_width=True)

# Botão para exportar os detalhes para Excel (os dois juntos)
import io

def exportar_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_det_horas_display.to_excel(writer, index=False, sheet_name='Horas_Extras')
        df_det_fora_display.to_excel(writer, index=False, sheet_name='Fora_do_Turno')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

excel_data = exportar_excel()
st.download_button(
    label="📥 Exportar Detalhes para Excel",
    data=excel_data,
    file_name=f"Detalhes_Ponto_{mes_selecionado}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
