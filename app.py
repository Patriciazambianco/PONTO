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
    if pd.isna(minutos) or minutos <= 0:
        return "00:00"
    h = int(minutos // 60)
    m = int(minutos % 60)
    return f"{h:02d}:{m:02d}"

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
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute)
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

# Ranking Horas Extras - Top 20
ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index(name='Total_minutos_extras')
    .sort_values(by='Total_minutos_extras', ascending=False)
    .head(20)
)
ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutos_para_hms)

# Ranking Fora do Turno - Top 20
ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
    .sort_values(by='Dias_fora_turno', ascending=False)
    .head(20)
)

# Detalhamento
top_nomes = pd.concat([ranking_horas['Nome'], ranking_fora_turno['Nome']]).drop_duplicates().tolist()
df_offensores = df_mes[df_mes['Nome'].isin(top_nomes) & (df_mes['Hora_extra'] | df_mes['Entrada_fora_turno'])]

# Mostrar detalhe primeiro
st.markdown("### 🔎 Detalhamento por Funcionário")
for nome in top_nomes:
    df_func = df_offensores[df_offensores['Nome'] == nome]
    if df_func.empty:
        continue
    with st.expander(f"{nome} - {len(df_func)} infrações"):
        st.dataframe(
            df_func[[
                'Data_fmt', 'Entrada_fmt', 'Saida_fmt',
                'Turnos.ENTRADA', 'Turnos.SAIDA',
                'Minutos_extras', 'Hora_extra', 'Entrada_fora_turno'
            ]].rename(columns={
                'Data_fmt': 'Data',
                'Entrada_fmt': 'Entrada',
                'Saida_fmt': 'Saída',
                'Turnos.ENTRADA': 'Turno Entrada',
                'Turnos.SAIDA': 'Turno Saída',
                'Minutos_extras': 'Minutos Extra',
                'Hora_extra': 'Hora Extra',
                'Entrada_fora_turno': 'Fora do Turno'
            }),
            use_container_width=True
        )

# Rankings lado a lado
col1, col2 = st.columns(2)
with col1:
    st.subheader(f"⏰ Top 20 - Horas Extras ({mes_selecionado})")
    st.dataframe(
        ranking_horas.rename(columns={'Nome': 'Funcionário', 'Horas_fmt': 'Horas Extras'}),
        use_container_width=True
    )
with col2:
    st.subheader(f"🚨 Top 20 - Fora do Turno ({mes_selecionado})")
    st.dataframe(
        ranking_fora_turno.rename(columns={'Nome': 'Funcionário'}),
        use_container_width=True
    )

# Gráficos
fig1 = px.bar(
    ranking_horas,
    x='Horas_fmt', y='Nome',
    orientation='h',
    title='Top 20 - Horas Extras',
    labels={'Horas_fmt': 'Horas', 'Nome': 'Funcionário'},
    text='Horas_fmt'
)
fig1.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.bar(
    ranking_fora_turno,
    x='Dias_fora_turno', y='Nome',
    orientation='h',
    title='Top 20 - Fora do Turno',
    labels={'Dias_fora_turno': 'Dias', 'Nome': 'Funcionário'},
    text='Dias_fora_turno'
)
fig2.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig2, use_container_width=True)

# Botão de exportação
st.markdown("---")
st.subheader("📥 Exportar para Excel")

from io import BytesIO
import xlsxwriter

def gerar_excel(df_horas, df_fora, df_detalhe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_horas.to_excel(writer, index=False, sheet_name="Ranking_Horas_Extras")
        df_fora.to_excel(writer, index=False, sheet_name="Ranking_Fora_Turno")
        df_detalhe.to_excel(writer, index=False, sheet_name="Detalhamento")
    output.seek(0)
    return output

df_export_horas = ranking_horas[['Nome', 'Total_minutos_extras', 'Horas_fmt']].rename(
    columns={'Nome': 'Funcionário', 'Total_minutos_extras': 'Minutos', 'Horas_fmt': 'Horas'}
)
df_export_fora = ranking_fora_turno.rename(columns={'Nome': 'Funcionário'})
df_export_detalhe = df_offensores[['Nome', 'Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Minutos_extras', 'Hora_extra', 'Entrada_fora_turno']]

excel_data = gerar_excel(df_export_horas, df_export_fora, df_export_detalhe)
st.download_button("📤 Baixar Rankings e Detalhes", data=excel_data, file_name="Relatorio_Ponto.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
