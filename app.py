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
    try:
        if minutos is None or pd.isna(minutos) or minutos <= 0:
            return "00:00:00"
        minutos_int = int(round(minutos))
        h = minutos_int // 60
        m = minutos_int % 60
        return f"{h:02d}:{m:02d}:00"
    except:
        return "00:00:00"

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

# Carregar e analisar dados
df = carregar_dados()
df = analisar_ponto(df)

# Seleção de mês
meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses_disponiveis)
df_mes = df[df['Mes_Ano'] == mes_selecionado]

# Rankings
ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index(name='Total_minutos_extras')
)
ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutos_para_hms)
ranking_horas = ranking_horas.sort_values(by='Total_minutos_extras', ascending=False)

ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
).sort_values(by='Dias_fora_turno', ascending=False)

# Exibir rankings
col1, col2 = st.columns(2)
with col1:
    st.subheader(f"⏰ Ranking - Total de Horas Extras ({mes_selecionado})")
    st.dataframe(ranking_horas.rename(columns={'Nome': 'Funcionário', 'Horas_fmt': 'Horas Extras'}), use_container_width=True)

with col2:
    st.subheader(f"🚨 Ranking - Dias Fora do Turno ({mes_selecionado})")
    st.dataframe(ranking_fora_turno.rename(columns={'Nome': 'Funcionário'}), use_container_width=True)

# Detalhamento ofensores
top50_nomes = pd.concat([ranking_horas.head(50)['Nome'], ranking_fora_turno.head(50)['Nome']]).drop_duplicates().tolist()
df_offensores = df_mes[(df_mes['Nome'].isin(top50_nomes)) & (df_mes['Hora_extra'] | df_mes['Entrada_fora_turno'])]

st.markdown("---")
st.subheader(f"🔍 Detalhamento dos 50 maiores ofensores em horas extras ou fora do turno ({mes_selecionado})")

for nome in top50_nomes:
    df_func = df_offensores[df_offensores['Nome'] == nome]
    if df_func.empty:
        continue
    with st.expander(f"{nome} - {len(df_func)} infrações"):
        st.dataframe(
            df_func[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Hora_extra', 'Entrada_fora_turno']].rename(
                columns={
                    'Data_fmt': 'Data',
                    'Entrada_fmt': 'Entrada',
                    'Saida_fmt': 'Saída',
                    'Turnos.ENTRADA': 'Turno Entrada',
                    'Turnos.SAIDA': 'Turno Saída',
                    'Hora_extra': 'Hora Extra',
                    'Entrada_fora_turno': 'Fora do Turno'
                }
            ),
            use_container_width=True
        )

# Gráficos
fig_horas = px.bar(ranking_horas, x='Total_minutos_extras', y='Nome', orientation='h',
    labels={'Total_minutos_extras': 'Minutos', 'Nome': 'Funcionário'}, text='Horas_fmt',
    title='Minutos de Horas Extras por Funcionário')
fig_horas.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig_horas, use_container_width=True)

fig_fora = px.bar(ranking_fora_turno, x='Dias_fora_turno', y='Nome', orientation='h',
    labels={'Dias_fora_turno': 'Dias Fora do Turno', 'Nome': 'Funcionário'}, text='Dias_fora_turno',
    title='Dias Fora do Turno por Funcionário')
fig_fora.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig_fora, use_container_width=True)

# Relatório consolidado
with st.expander("📁 Relatório Consolidado de Jornada e Horas Extras"):
    df['Horas_extras'] = df['Minutos_extras'].apply(lambda m: round(m / 60, 2) if m > 0 else 0)
    df['Mes'] = df['Data'].dt.strftime('%b')
    df['Deslocamento'] = df.apply(
        lambda row: f"{row['Entrada_fmt']} - {row['Saida_fmt']} (Jornada: {row['Turnos.ENTRADA'].strftime('%H:%M')} - {row['Turnos.SAIDA'].strftime('%H:%M')})"
        if pd.notnull(row['Entrada 1']) and pd.notnull(row['Saída 1']) and pd.notnull(row['Turnos.ENTRADA']) and pd.notnull(row['Turnos.SAIDA']) else '',
        axis=1
    )

    pivot = df.pivot_table(index='Nome', columns='Mes', values='Horas_extras', aggfunc='sum').fillna(0)
    deslocamentos = df.groupby('Nome')['Deslocamento'].apply(lambda x: ', '.join(x)).reset_index()
    final = pivot.merge(deslocamentos, on='Nome', how='left').rename(columns={'Deslocamento': 'Deslocamento da Jornada'})

    st.dataframe(final, use_container_width=True)

    excel_bytes = BytesIO()
    with pd.ExcelWriter(excel_bytes, engine='xlsxwriter') as writer:
        final.to_excel(writer, index=False, sheet_name='Relatorio Consolidado')
    st.download_button("📅 Baixar Excel Consolidado", data=excel_bytes.getvalue(), file_name="relatorio_consolidado.xlsx")
