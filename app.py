import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="📊 Relatório de Ponto")

# -------------------- FUNÇÕES --------------------
@st.cache_data
def carregar_dados():
    url = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"
    response = requests.get(url)
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
        if (row['Minutos_trabalhados'] is not None and row['Minutos_turno_saida'] is not None and row['Minutos_turno_entrada'] is not None)
        else 0,
        axis=1
    )
    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['AnoMes'] = df['Data'].dt.to_period('M').astype(str)
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m/%Y')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    return df

# -------------------- CARREGAR E ANALISAR --------------------
df = carregar_dados()
df = analisar_ponto(df)

# -------------------- FILTROS E CARDS --------------------
st.title("📅 Relatório de Ponto – Infrações Mensais")
meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
todos = st.checkbox("Selecionar todos os meses", value=True)
meses_selecionados = meses_disponiveis if todos else st.multiselect("Meses:", meses_disponiveis, default=meses_disponiveis[:1])
df_filtrado = df[df['AnoMes'].isin(meses_selecionados)]

# Cards com totais
col1, col2, col3 = st.columns(3)
col1.metric("Funcionários com Hora Extra", df_filtrado[df_filtrado['Hora_extra']]['Nome'].nunique())
col2.metric("Fora do Turno", df_filtrado[df_filtrado['Entrada_fora_turno']]['Nome'].nunique())
col3.metric("Total de Registros", len(df_filtrado))

# -------------------- RANKINGS GRÁFICOS --------------------
col1, col2 = st.columns(2)
with col1:
    st.subheader("🔥 Ranking Horas Extras (Total em Horas)")
    ranking_horas = df_filtrado[df_filtrado['Hora_extra']].groupby('Nome').agg({'Minutos_extras': 'sum'}).reset_index()
    ranking_horas['Horas_fmt'] = ranking_horas['Minutos_extras'].apply(minutes_to_hms)
    fig = px.bar(
    ranking_horas.sort_values(by='Minutos_extras'),
    x='Minutos_extras', y='Nome', orientation='h',
    labels={'Minutos_extras': 'Minutos'},
    hover_data=['Horas_fmt'],
    template='plotly_white'
), x='Minutos_extras', y='Nome', orientation='h', labels={'Minutos_extras':'Minutos'}, hover_data=['Horas_fmt'])
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("⏰ Ranking Dias Fora do Turno")
    ranking_turno = df_filtrado[df_filtrado['Entrada_fora_turno']].groupby('Nome').size().reset_index(name='Dias')
    fig2 = px.bar(
    ranking_turno.sort_values(by='Dias'),
    x='Dias', y='Nome', orientation='h',
    template='plotly_white'
), x='Dias', y='Nome', orientation='h')
    st.plotly_chart(fig2, use_container_width=True)

# -------------------- DETALHAMENTO EXPANDIDO --------------------
st.markdown("---")
st.subheader("📋 Detalhamento por Funcionário")

infratores = df_filtrado[(df_filtrado['Hora_extra']) | (df_filtrado['Entrada_fora_turno'])]
top_50 = infratores['Nome'].value_counts().head(50).index
for nome in top_50:
    with st.expander(f"👤 {nome}"):
        pessoa = infratores[infratores['Nome'] == nome].copy()
        pessoa['Horas_fmt'] = pessoa['Minutos_extras'].apply(minutes_to_hms)
        pessoa['Status'] = pessoa.apply(lambda row: "Hora Extra" if row['Hora_extra'] else ("Fora do Turno" if row['Entrada_fora_turno'] else "OK"), axis=1)
        st.dataframe(
            pessoa[['AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_fmt', 'Status']].sort_values(by='Data_fmt'),
            use_container_width=True
        ), use_container_width=True)

# -------------------- DOWNLOAD --------------------
st.markdown("---")
if st.button("📥 Exportar Detalhes para Excel"):
    export = infratores[['Nome', 'AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Minutos_extras']]
    export['Horas_fmt'] = export['Minutos_extras'].apply(minutes_to_hms)
    excel_io = BytesIO()
    export.to_excel(excel_io, index=False)
    st.download_button("📄 Baixar Arquivo Excel", data=excel_io.getvalue(), file_name="detalhes_infracoes.xlsx")
