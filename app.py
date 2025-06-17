import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Função utilitária global para converter minutos em HH:MM:SS
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

    # Ajuste das datas e horários
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

# Agrupamento para trazer jornada só uma vez
ranking_horas = (
    df_mes[df_mes['Hora_extra']]
    .groupby(['Nome', 'Turnos.ENTRADA', 'Turnos.SAIDA'])
    .agg({'Minutos_extras': 'sum'})
    .reset_index()
    .rename(columns={'Minutos_extras': 'Total_minutos_extras'})
)
ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutos_para_hms)
ranking_horas = ranking_horas.sort_values(by='Total_minutos_extras', ascending=False)

ranking_fora_turno = (
    df_mes[df_mes['Entrada_fora_turno']]
    .groupby(['Nome', 'Turnos.ENTRADA', 'Turnos.SAIDA'])
    .size()
    .reset_index(name='Dias_fora_turno')
)
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias_fora_turno', ascending=False)

col1, col2 = st.columns(2)

with col1:
    st.subheader(f"⏰ Ranking - Total de Horas Extras ({mes_selecionado})")
    st.dataframe(
        ranking_horas.rename(columns={
            'Nome': 'Funcionário',
            'Horas_fmt': 'Horas Extras',
            'Turnos.ENTRADA': 'Turno Entrada',
            'Turnos.SAIDA': 'Turno Saída'
        }),
        use_container_width=True
    )

with col2:
    st.subheader(f"🚨 Ranking - Dias Fora do Turno ({mes_selecionado})")
    st.dataframe(
        ranking_fora_turno.rename(columns={
            'Nome': 'Funcionário',
            'Turnos.ENTRADA': 'Turno Entrada',
            'Turnos.SAIDA': 'Turno Saída'
        }),
        use_container_width=True
    )

st.markdown("---")
st.subheader(f"🔍 Detalhamento dos 50 maiores ofensores em horas extras ou fora do turno ({mes_selecionado})")

top50_nomes = pd.concat([
    ranking_horas.head(50)['Nome'],
    ranking_fora_turno.head(50)['Nome']
]).drop_duplicates().tolist()

df_offensores = df_mes[(df_mes['Nome'].isin(top50_nomes)) & (df_mes['Hora_extra'] | df_mes['Entrada_fora_turno'])]

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

fig_horas = px.bar(
    ranking_horas,
    x='Total_minutos_extras',
    y='Nome',
    orientation='h',
    labels={'Total_minutos_extras': 'Minutos', 'Nome': 'Funcionário'},
    title='Minutos de Horas Extras por Funcionário',
    text=ranking_horas['Horas_fmt']
)
fig_horas.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig_horas, use_container_width=True)

fig_fora = px.bar(
    ranking_fora_turno,
    x='Dias_fora_turno',
    y='Nome',
    orientation='h',
    labels={'Dias_fora_turno': 'Dias Fora do Turno', 'Nome': 'Funcionário'},
    title='Dias Fora do Turno por Funcionário',
    text=ranking_fora_turno['Dias_fora_turno']
)
fig_fora.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor='white')
st.plotly_chart(fig_fora, use_container_width=True)

# Exportar Excel
import io

def exportar_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        ranking_horas.rename(columns={
            'Nome': 'Funcionário',
            'Horas_fmt': 'Horas Extras',
            'Turnos.ENTRADA': 'Turno Entrada',
            'Turnos.SAIDA': 'Turno Saída'
        }).to_excel(writer, index=False, sheet_name='Horas Extras')

        ranking_fora_turno.rename(columns={
            'Nome': 'Funcionário',
            'Turnos.ENTRADA': 'Turno Entrada',
            'Turnos.SAIDA': 'Turno Saída'
        }).to_excel(writer, index=False, sheet_name='Dias Fora do Turno')

        df_offensores.rename(columns={
            'Data_fmt': 'Data',
            'Entrada_fmt': 'Entrada',
            'Saida_fmt': 'Saída',
            'Turnos.ENTRADA': 'Turno Entrada',
            'Turnos.SAIDA': 'Turno Saída',
            'Hora_extra': 'Hora Extra',
            'Entrada_fora_turno': 'Fora do Turno'
        })[
            ['Nome', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Hora_extra', 'Entrada_fora_turno']
        ].to_excel(writer, index=False, sheet_name='Detalhamento Ofensores')

        writer.save()
        processed_data = output.getvalue()
    return processed_data

st.markdown("---")
if st.button("⬇️ Exportar relatório consolidado para Excel"):
    excel_data = exportar_excel()
    st.download_button(label="Clique para baixar o Excel", data=excel_data, file_name=f"relatorio_ponto_{mes_selecionado}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
