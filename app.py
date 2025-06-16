import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import timedelta
import plotly.express as px

# URL do arquivo Excel no GitHub raw
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Ajusta formatos de data e hora
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], errors='coerce').dt.time

    return df

def diff_minutes(t1, t2):
    if pd.isna(t1) or pd.isna(t2) or t1 is None or t2 is None:
        return 0
    dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    diff = dt2 - dt1
    return diff.total_seconds() / 60

def fora_do_turno(entrada_real, entrada_turno):
    if entrada_real is None or entrada_turno is None:
        return False
    diff = abs(diff_minutes(entrada_real, entrada_turno))
    return diff > 60  # fora do turno se mais que 1h de diferença

def calcula_hora_extra(entrada_real, saida_real, entrada_turno, saida_turno):
    if None in (entrada_real, saida_real, entrada_turno, saida_turno):
        return 0
    minutos_trabalhados = diff_minutes(entrada_real, saida_real)
    minutos_turno = diff_minutes(entrada_turno, saida_turno)
    extra = minutos_trabalhados - minutos_turno
    return extra if extra > 15 else 0  # só conta hora extra acima de 15 minutos

def analisar_ponto(df):
    # Aplica flags
    df['Fora_do_turno'] = df.apply(lambda r: fora_do_turno(r['Entrada 1'], r['Turnos.ENTRADA']), axis=1)
    df['Hora_extra'] = df.apply(
        lambda r: calcula_hora_extra(r['Entrada 1'], r['Saída 1'], r['Turnos.ENTRADA'], r['Turnos.SAIDA']),
        axis=1
    )
    df['Hora_extra_h'] = df['Hora_extra'] / 60  # em horas

    # Reincidência por funcionário (contagem de dias fora do turno e hora extra)
    reincidentes = df.groupby('Funcionario').agg(
        fora_do_turno_count=('Fora_do_turno', 'sum'),
        hora_extra_count=('Hora_extra', lambda x: (x > 0).sum()),
        total_hora_extra=('Hora_extra_h', 'sum')
    ).reset_index()

    # Só quem teve algum tipo de erro
    reincidentes = reincidentes[(reincidentes['fora_do_turno_count'] > 0) | (reincidentes['hora_extra_count'] > 0)]

    # Ordena pelo total de reincidências (fora do turno + hora extra count)
    reincidentes['total_reincidencias'] = reincidentes['fora_do_turno_count'] + reincidentes['hora_extra_count']
    reincidentes = reincidentes.sort_values(by='total_reincidencias', ascending=False)

    return df, reincidentes

def medalha(pos):
    if pos == 0:
        return "🥇"
    elif pos == 1:
        return "🥈"
    elif pos == 2:
        return "🥉"
    else:
        return ""

# --- Código principal Streamlit ---

st.set_page_config(page_title="Análise de Ponto", layout="wide")

st.title("📊 Análise de Ponto com Ranking de Reincidentes")

df = carregar_dados()
df, reincidentes = analisar_ponto(df)

# Filtro por período
opcoes_periodo = {
    "Últimos 30 dias": 30,
    "Mês Atual": None,
    "Tudo": None
}

periodo = st.selectbox("Selecione o período:", list(opcoes_periodo.keys()))

if periodo == "Últimos 30 dias":
    df_periodo = df[df['Data'] >= (pd.Timestamp.today() - pd.Timedelta(days=30))]
elif periodo == "Mês Atual":
    hoje = pd.Timestamp.today()
    df_periodo = df[(df['Data'].dt.year == hoje.year) & (df['Data'].dt.month == hoje.month)]
else:
    df_periodo = df.copy()

# Atualiza reincidentes pelo período filtrado
_, reincidentes_periodo = analisar_ponto(df_periodo)

# Ranking reincidentes
st.subheader("🏆 Ranking de Reincidentes")
reincidentes_periodo = reincidentes_periodo.reset_index(drop=True)
reincidentes_periodo.index.name = "Posição"
reincidentes_periodo['Medalha'] = reincidentes_periodo.index.map(medalha)

# Colorindo linhas com st.dataframe não tem suporte nativo, usa st.table com styler
def highlight_medal(s):
    color = ""
    if s.name == 0:
        color = "#FFD700"  # Ouro - dourado
    elif s.name == 1:
        color = "#C0C0C0"  # Prata
    elif s.name == 2:
        color = "#CD7F32"  # Bronze
    return ['background-color: {}'.format(color) if color else '' for _ in s]

ranking_display = reincidentes_periodo[['Medalha', 'Funcionario', 'fora_do_turno_count', 'hora_extra_count', 'total_hora_extra']]
ranking_display = ranking_display.rename(columns={
    'Funcionario': 'Funcionário',
    'fora_do_turno_count': 'Fora do Turno (dias)',
    'hora_extra_count': 'Dias com Hora Extra',
    'total_hora_extra': 'Horas Extras (h)'
})

st.table(ranking_display.style.apply(highlight_medal, axis=1))

# Relatório detalhado ao clicar no funcionário (simula com selectbox)
st.subheader("📅 Detalhes do Funcionário")

func = st.selectbox("Selecione o funcionário para detalhes:", reincidentes_periodo['Funcionario'].tolist())

if func:
    df_func = df_periodo[df_periodo['Funcionario'] == func].copy()

    df_func['Data'] = df_func['Data'].dt.strftime('%d/%m/%Y')
    df_func['Entrada 1'] = df_func['Entrada 1'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
    df_func['Saída 1'] = df_func['Saída 1'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
    df_func['Turnos.ENTRADA'] = df_func['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
    df_func['Turnos.SAIDA'] = df_func['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')

    # Mostra apenas registros fora do turno ou com hora extra
    df_func = df_func[(df_func['Fora_do_turno']) | (df_func['Hora_extra'] > 0)]

    st.dataframe(df_func[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Fora_do_turno', 'Hora_extra_h']])

# Gráfico interativo: total de fora do turno e hora extra por dia
st.subheader("📈 Gráfico de ocorrências por dia")

df_dia = df_periodo.groupby('Data').agg(
    fora_do_turno_total=('Fora_do_turno', 'sum'),
    hora_extra_total=('Hora_extra_h', 'sum')
).reset_index()

fig = px.bar(df_dia.melt(id_vars='Data', value_vars=['fora_do_turno_total', 'hora_extra_total']),
             x='Data', y='value', color='variable',
             labels={'value': 'Quantidade', 'variable': 'Tipo', 'Data': 'Data'},
             title="Ocorrências de Fora do Turno e Hora Extra por Dia",
             color_discrete_map={
                'fora_do_turno_total': 'orange',
                'hora_extra_total': 'green'
             })

st.plotly_chart(fig, use_container_width=True)

# Botão para baixar relatório em Excel
from io import BytesIO

def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Relatório')
    writer.save()
    processed_data = output.getvalue()
    return processed_data

st.subheader("📥 Download do relatório filtrado")

dados_download = df_periodo.copy()
dados_download['Data'] = dados_download['Data'].dt.strftime('%d/%m/%Y')
dados_download['Entrada 1'] = dados_download['Entrada 1'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
dados_download['Saída 1'] = dados_download['Saída 1'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
dados_download['Turnos.ENTRADA'] = dados_download['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
dados_download['Turnos.SAIDA'] = dados_download['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')

excel_data = to_excel(dados_download)

st.download_button(label='⬇️ Baixar Excel', data=excel_data, file_name='relatorio_ponto.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

