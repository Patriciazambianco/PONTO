import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

# URL do arquivo Excel no GitHub
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Paleta personalizada
COR_AZUL = "#004aad"
COR_VERDE = "#009973"
COR_LARANJA = "#ff7f0e"
COR_VERMELHO = "#d62728"

# Função para baixar dados
@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    # Converter horas (com cuidado para erros)
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time
    return df

# Função para calcular diferença em minutos entre duas horas
def diff_minutes(t1, t2):
    if pd.isnull(t1) or pd.isnull(t2):
        return None
    dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    diff = (dt2 - dt1).total_seconds() / 60
    if diff < 0:  # hora passada da meia-noite
        diff += 24*60
    return diff

# Função para identificar fora do turno (mais de 1 hora antes ou depois do turno)
def fora_do_turno(entrada_real, turno_entrada):
    if pd.isnull(entrada_real) or pd.isnull(turno_entrada):
        return False
    dt_real = timedelta(hours=entrada_real.hour, minutes=entrada_real.minute, seconds=entrada_real.second)
    dt_turno = timedelta(hours=turno_entrada.hour, minutes=turno_entrada.minute, seconds=turno_entrada.second)
    diff = abs((dt_real - dt_turno).total_seconds()) / 60
    return diff > 60  # mais de 1 hora

# Análise principal
def analisar_ponto(df):
    df = df.copy()
    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )
    df['Fora_do_turno'] = df.apply(
        lambda row: fora_do_turno(row['Entrada 1'], row['Turnos.ENTRADA']),
        axis=1
    )
    df['Hora_extra'] = df.apply(
        lambda row: diff_minutes(row['Turnos.SAIDA'], row['Saída 1']) if row['Saída 1'] and row['Turnos.SAIDA'] else 0,
        axis=1
    )
    df['Hora_extra'] = df['Hora_extra'].apply(lambda x: x if x > 15 else 0)  # só conta hora extra > 15 min

    # Dias com erro (fora do turno ou hora extra)
    df['Erro'] = df['Fora_do_turno'] | (df['Hora_extra'] > 0)

    return df

# Função para formatar datas
def formatar_data(dt):
    return dt.strftime('%d/%m/%Y')

# Ranking reincidentes
def ranking_reincidentes(df):
    df_errados = df[df['Erro']]
    ranking = df_errados.groupby('Funcionário').agg(
        total_erros=pd.NamedAgg(column='Erro', aggfunc='sum'),
        total_hora_extra=pd.NamedAgg(column='Hora_extra', aggfunc='sum')
    ).reset_index()
    ranking = ranking.sort_values(by=['total_erros', 'total_hora_extra'], ascending=False)
    return ranking

# Função para medalhas
def medalha(n):
    if n == 1:
        return "🥇"
    elif n == 2:
        return "🥈"
    elif n == 3:
        return "🥉"
    else:
        return ""

# Início do app
st.set_page_config(page_title="Análise de Ponto", layout="wide")

st.title("📊 Análise de Ponto - Ranking de Reincidentes")

df = carregar_dados()
df = analisar_ponto(df)

# Filtro por mês
meses_disponiveis = df['Data'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses_disponiveis.astype(str))

df['MesAno'] = df['Data'].dt.to_period('M').astype(str)
df_filtrado = df[df['MesAno'] == mes_selecionado]

ranking = ranking_reincidentes(df_filtrado).reset_index(drop=True)
ranking['Medalha'] = [medalha(i+1) for i in ranking.index]

# Mostrar ranking com cores
def cor_linha(row):
    if row['Medalha'] == "🥇":
        return f'background-color: {COR_VERDE}; color: white; font-weight: bold;'
    elif row['Medalha'] == "🥈":
        return f'background-color: {COR_AZUL}; color: white; font-weight: bold;'
    elif row['Medalha'] == "🥉":
        return f'background-color: {COR_LARANJA}; color: white; font-weight: bold;'
    elif row['total_erros'] > 5:
        return f'background-color: {COR_VERMELHO}; color: white; font-weight: bold;'
    else:
        return ''

st.markdown("### 🏆 Ranking dos Reincidentes (Fora do turno ou Hora Extra)")

st.dataframe(
    ranking.style.applymap(lambda _: '', subset=['Funcionário'])
           .apply(lambda row: [cor_linha(row)]*len(ranking.columns), axis=1)
)

# Detalhes ao clicar no nome
st.markdown("### Detalhes dos Erros")

nome_selecionado = st.selectbox("Selecione o funcionário para ver os dias com erros:", ranking['Funcionário'] if not ranking.empty else [])

if nome_selecionado:
    df_erros_func = df_filtrado[(df_filtrado['Funcionário'] == nome_selecionado) & (df_filtrado['Erro'])]
    df_erros_func_display = df_erros_func[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Fora_do_turno', 'Hora_extra']].copy()
    df_erros_func_display['Data'] = df_erros_func_display['Data'].dt.strftime('%d/%m/%Y')
    st.dataframe(df_erros_func_display)

# Gráfico animado de horas extras ao longo do mês
fig = px.bar(
    df_filtrado.groupby(['Data', 'Funcionário'])['Hora_extra'].sum().reset_index(),
    x='Data',
    y='Hora_extra',
    color='Funcionário',
    animation_frame=df_filtrado['Data'].dt.strftime('%d/%m/%Y'),
    title='Horas Extras ao Longo do Mês',
    color_discrete_sequence=[COR_AZUL, COR_VERDE, COR_LARANJA, COR_VERMELHO]
)
st.plotly_chart(fig, use_container_width=True)

# Botão para baixar relatório filtrado
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatório')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

dados_para_baixar = df_filtrado.copy()
dados_para_baixar['Data'] = dados_para_baixar['Data'].dt.strftime('%d/%m/%Y')

arquivo_excel = to_excel(dados_para_baixar)

st.download_button(
    label="📥 Baixar Relatório Excel",
    data=arquivo_excel,
    file_name=f"relatorio_ponto_{mes_selecionado}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
