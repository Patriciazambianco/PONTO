import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
import plotly.express as px
import openpyxl
import io

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# --- Funções auxiliares ---

def diff_minutes(t1, t2):
    if pd.isna(t1) or pd.isna(t2):
        return None
    dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    diff = dt2 - dt1
    return diff.total_seconds() / 60

def analisar_ponto(df):
    # Tratar horários
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], errors='coerce').dt.time

    # Calcular minutos trabalhados e do turno
    df['Minutos_trabalhados'] = df.apply(
        lambda r: diff_minutes(r['Entrada 1'], r['Saída 1']) if r['Entrada 1'] and r['Saída 1'] else None,
        axis=1)
    df['Minutos_turno'] = df.apply(
        lambda r: diff_minutes(r['Turnos.ENTRADA'], r['Turnos.SAIDA']) if r['Turnos.ENTRADA'] and r['Turnos.SAIDA'] else None,
        axis=1)

    # Fora do turno: entrada com diferença maior que 1 hora para mais ou menos do turno
    def fora_do_turno(entrada_real, entrada_turno):
        if entrada_real is None or entrada_turno is None:
            return False
        diff = abs(diff_minutes(entrada_real, entrada_turno))
        return diff > 60

    df['Fora_do_turno'] = df.apply(lambda r: fora_do_turno(r['Entrada 1'], r['Turnos.ENTRADA']), axis=1)

    # Hora extra (em minutos) só conta se passar de 15 min
    df['Hora_extra'] = df.apply(
        lambda r: max(r['Minutos_trabalhados'] - r['Minutos_turno'], 0) if pd.notnull(r['Minutos_trabalhados']) and pd.notnull(r['Minutos_turno']) else 0,
        axis=1)
    df['Hora_extra'] = df['Hora_extra'].apply(lambda x: x if x > 15 else 0)
    df['Hora_extra_horas'] = (df['Hora_extra'] / 60).round(2)

    # Reincidências por funcionário
    df['Reincidente_fora_turno'] = df.groupby('Funcionario')['Fora_do_turno'].transform('sum')
    df['Reincidente_hora_extra'] = df.groupby('Funcionario')['Hora_extra'].transform(lambda x: (x > 0).sum())

    return df

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo = BytesIO(response.content)
    df = pd.read_excel(arquivo)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    return df

def gerar_ranking(df):
    ranking = df.groupby('Funcionario').agg({
        'Fora_do_turno': 'sum',
        'Hora_extra': lambda x: (x > 0).sum(),
        'Hora_extra_horas': 'sum'
    }).reset_index()

    ranking = ranking.rename(columns={
        'Fora_do_turno': 'Qtd Fora do Turno',
        'Hora_extra': 'Qtd Dias Hora Extra',
        'Hora_extra_horas': 'Total de Horas Extras'
    })

    ranking = ranking.sort_values(by=['Qtd Fora do Turno', 'Qtd Dias Hora Extra', 'Total de Horas Extras'], ascending=False)

    # Medalhas (ouro, prata, bronze) para fora do turno (exemplo simples)
    ranking['Medalha'] = ''
    if len(ranking) >= 1:
        ranking.loc[ranking.index[0], 'Medalha'] = '🥇'
    if len(ranking) >= 2:
        ranking.loc[ranking.index[1], 'Medalha'] = '🥈'
    if len(ranking) >= 3:
        ranking.loc[ranking.index[2], 'Medalha'] = '🥉'

    return ranking

def filtrar_periodo(df, periodo):
    hoje = datetime.now()
    if periodo == "Últimos 30 dias":
        inicio = hoje - timedelta(days=30)
    elif periodo == "Mês Atual":
        inicio = datetime(hoje.year, hoje.month, 1)
    else:
        inicio = df['Data'].min()
    df_filtrado = df[df['Data'] >= inicio]
    return df_filtrado

def exportar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatório Ponto')
    return output.getvalue()

# --- App Streamlit ---

st.set_page_config(page_title="Análise de Ponto", layout="wide")

st.title("📊 Análise de Ponto")

# Filtro de período
periodo = st.selectbox("Selecione o período", ["Últimos 30 dias", "Mês Atual", "Desde o início"])

# Carregar dados e filtrar
df = carregar_dados()
df = filtrar_periodo(df, periodo)

# Analisar ponto
df = analisar_ponto(df)

# Ranking reincidentes
ranking = gerar_ranking(df)

col1, col2 = st.columns([3, 5])

with col1:
    st.subheader("🏆 Ranking de Reincidentes")
    st.dataframe(ranking.style.applymap(lambda v: 'background-color: #FFD700' if '🥇' in str(v) else
                                               '#C0C0C0' if '🥈' in str(v) else
                                               '#CD7F32' if '🥉' in str(v) else '',
                                      subset=['Medalha']))

with col2:
    st.subheader("📈 Gráfico Hora Extra por Funcionário")
    fig = px.bar(ranking, x='Funcionario', y='Total de Horas Extras',
                 color='Total de Horas Extras', color_continuous_scale='greens',
                 labels={'Total de Horas Extras': 'Horas Extras'},
                 title="Horas Extras por Funcionário")
    st.plotly_chart(fig, use_container_width=True)

# Detalhes ao clicar no nome
st.markdown("### Detalhes por Funcionário")

funcionario_selecionado = st.selectbox("Selecione o funcionário", ranking['Funcionario'].unique())

detalhes = df[df['Funcionario'] == funcionario_selecionado][
    ['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Fora_do_turno', 'Hora_extra_horas']
]

# Formatar data e horários
detalhes['Data'] = detalhes['Data'].dt.strftime('%d/%m/%Y')
detalhes['Entrada 1'] = detalhes['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
detalhes['Saída 1'] = detalhes['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
detalhes['Turnos.ENTRADA'] = detalhes['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
detalhes['Turnos.SAIDA'] = detalhes['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

st.dataframe(detalhes.style.applymap(lambda v: 'background-color: #FFA07A' if isinstance(v, bool) and v else '', subset=['Fora_do_turno']))

# Botão para baixar relatório
st.markdown("---")
st.download_button(
    label="📥 Baixar relatório Excel",
    data=exportar_excel(df),
    file_name=f"relatorio_ponto_{datetime.now().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
