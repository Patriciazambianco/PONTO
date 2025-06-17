import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide", page_title="Relatório de Ponto - Horas Extras e Fora do Turno")
st.title("\U0001F4CA Relatório de Ponto - Horas Extras e Fora do Turno")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_hms(minutos):
    if minutos is None or pd.isna(minutos) or minutos <= 0:
        return "00:00:00"
    h = minutos // 60
    m = minutos % 60
    return f"{int(h):02d}:{int(m):02d}:00"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
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
    df['Min_Entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Min_Turno_Entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Min_Turno_Saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    df['Entrada_fora_turno'] = df.apply(
        lambda row: abs(row['Min_Entrada'] - row['Min_Turno_Entrada']) > 60
        if pd.notnull(row['Min_Entrada']) and pd.notnull(row['Min_Turno_Entrada']) else False, axis=1
    )

    df['Min_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )

    df['Min_extras'] = df.apply(
        lambda row: row['Min_trabalhados'] - (row['Min_Turno_Saida'] - row['Min_Turno_Entrada'])
        if row['Min_trabalhados'] is not None and row['Min_Turno_Entrada'] and row['Min_Turno_Saida'] else 0,
        axis=1
    )

    df['Hora_extra'] = df['Min_extras'] > 15
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Horas_fmt'] = df['Min_extras'].apply(minutos_para_hms)
    return df

df = analisar_ponto(carregar_dados())
meses = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes = st.selectbox("\U0001F4C5 Selecione o mês para análise:", meses)
coordenadores = sorted(df['COORDENADOR'].dropna().unique())
coordenador = st.selectbox("⚖️ Filtrar por Coordenador:", ["Todos"] + coordenadores)

df_mes = df[df['Mes_Ano'] == mes]
if coordenador != "Todos":
    df_mes = df_mes[df_mes['COORDENADOR'] == coordenador]

ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby('Nome')['Min_extras']
    .sum()
    .reset_index(name='Minutos_extras')
)
ranking_horas['Horas_fmt'] = ranking_horas['Minutos_extras'].apply(minutos_para_hms)
ranking_horas = ranking_horas.sort_values(by='Minutos_extras', ascending=False).head(20)

ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
    .sort_values(by='Dias_fora_turno', ascending=False)
    .head(20)
)

col1, col2 = st.columns(2)
with col1:
    st.subheader("🔥 Top 20 Horas Extras (Horas)")
    st.dataframe(ranking_horas[['Nome', 'Horas_fmt']], use_container_width=True)
    selecionado = st.selectbox("Selecionar Funcionário para Detalhes:", ranking_horas['Nome'].tolist())
    if selecionado:
        st.dataframe(df_mes[(df_mes['Nome'] == selecionado) & (df_mes['Hora_extra'])][
            ['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_fmt']
        ].rename(columns={
            'Data_fmt': 'Data', 'Entrada_fmt': 'Entrada', 'Saida_fmt': 'Saída', 'Horas_fmt': 'Horas Extras'
        }), use_container_width=True)

with col2:
    st.subheader("🚨 Top 20 Fora do Turno (Dias)")
    st.dataframe(ranking_fora_turno, use_container_width=True)
    selecionado2 = st.selectbox("Selecionar Funcionário para Fora do Turno:", ranking_fora_turno['Nome'].tolist())
    if selecionado2:
        st.dataframe(df_mes[(df_mes['Nome'] == selecionado2) & (df_mes['Entrada_fora_turno'])][
            ['Data_fmt', 'Entrada_fmt', 'Turnos.ENTRADA']
        ].rename(columns={
            'Data_fmt': 'Data', 'Entrada_fmt': 'Entrada Real', 'Turnos.ENTRADA': 'Entrada Esperada'
        }), use_container_width=True)

# Botão de Exportar Excel
import io
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    ranking_horas.to_excel(writer, index=False, sheet_name='Top Horas Extras')
    ranking_fora_turno.to_excel(writer, index=False, sheet_name='Top Fora Turno')
    df_mes[df_mes['Hora_extra']].to_excel(writer, index=False, sheet_name='Detalhes Horas')
    df_mes[df_mes['Entrada_fora_turno']].to_excel(writer, index=False, sheet_name='Detalhes Fora Turno')
    writer.save()

st.download_button(
    label="📄 Exportar Excel",
    data=output.getvalue(),
    file_name=f"Relatorio_Ponto_{mes}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
