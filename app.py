import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect
from groq import Groq
from dotenv import load_dotenv
import plotly.express as px

from security import validate_sql
from metadata import get_metadata


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="DataSage",
    page_icon="📊",
    layout="wide"
)

load_dotenv()


# =========================================================
# DATABASE
# =========================================================

engine = create_engine("sqlite:///datasage.db")


# =========================================================
# METADATA & SESSION STATE
# =========================================================

metadata = get_metadata()

if "history" not in st.session_state:
    st.session_state.history = []


# =========================================================
# GROQ
# =========================================================

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    st.error("GROQ_API_KEY not found in .env file.")
    st.stop()

client = Groq(
    api_key=groq_api_key
)


# =========================================================
# BUILD DATABASE SCHEMA
# =========================================================

@st.cache_data
def get_schema():

    inspector = inspect(engine)

    schema = ""

    for table in inspector.get_table_names():

        schema += f"\nTABLE: {table}\n"

        columns = inspector.get_columns(table)

        for col in columns:
            schema += f"- {col['name']}\n"

    return schema


schema = get_schema()


# =========================================================
# SQL GENERATION
# =========================================================

def generate_sql(question):

    prompt = f"""
You are DataSage, an expert SQLite analytics assistant.

Your job is to convert the user's natural-language question
into ONE safe, valid SQLite SELECT query.

DATABASE SCHEMA:
{schema}

DATASET METADATA:
{metadata}

USER QUESTION:
{question}

IMPORTANT RULES:

1. Return ONLY valid SQLite SQL.
2. Do NOT use markdown.
3. Do NOT provide explanations.
4. Never invent tables.
5. Never invent columns.
6. Use ONLY tables and columns present in the schema.
7. Use ONLY categorical values present in the metadata.
8. Country filters must use ISO-2 country codes.
9. If the user says India, use country code 'IN'.
10. If the user says United States or USA, use country code 'US'.
11. If the user says United Kingdom or UK, use country code 'GB'.
12. Age filters must use valid age groups from the metadata.
13. If the user says teenagers, interpret this as age group '18-24'.
14. If the user says young adults, interpret this as age group '25-34'.
15. If the user says seniors or older adults, interpret this as age group '65+'.
16. Never invent an AI tool name because this dataset contains ChatGPT usage data.
17. If the question asks about AI tools such as Gemini, Claude,
    Copilot, Grok, or Perplexity, explain through SQL only if
    such a column exists. Otherwise do not fabricate a result.
18. Use AVG(share_of_messages) when calculating average
    share across multiple months.
19. Use GROUP BY when comparing categories.
20. Use ORDER BY DESC when the user asks for top, highest,
    most popular, largest, or maximum.
21. Use ORDER BY month for time-based trends.
22. Use LIMIT 20 unless the user explicitly requests another limit.
23. Generate ONLY SELECT or WITH queries.
24. Never generate INSERT.
25. Never generate UPDATE.
26. Never generate DELETE.
27. Never generate DROP.
28. Never generate ALTER.
29. Never generate CREATE.
30. Never generate PRAGMA.
31. Never generate ATTACH or DETACH.
32. Do not use multiple SQL statements.
33. Do not use semicolons to execute multiple statements.
34. NEVER use LIMIT 1 when the question asks about topics,
    rankings, comparisons, or distributions. Always return
    all relevant ranked rows (use LIMIT 10 or LIMIT 20).
    Only use LIMIT 1 if the user explicitly says
    "the single most", "number 1", or "highest only".
35. When the user specifies an age range like '25 to 60',
    convert it to ALL matching age groups using OR conditions:
    age_group IN ('25-34', '35-44', '45-54', '55-64').
    Never collapse a range into a single age group.

Return ONLY SQL.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    sql = response.choices[0].message.content.strip()

    # Remove accidental markdown
    sql = sql.replace("```sql", "")
    sql = sql.replace("```", "")
    sql = sql.strip()

    return sql


# =========================================================
# AI INSIGHT GENERATION
# =========================================================

def generate_insight(question, df):

    if df.empty:
        return "No results were returned for this question."

    sample = df.head(15).to_string(index=False)

    prompt = f"""
You are a senior data analyst.

USER QUESTION:
{question}

QUERY RESULTS:
{sample}

Analyze the results and provide:

1. Key finding
2. Important trend or comparison
3. Business implication

Rules:
- Use only the information present in the results.
- Do not invent statistics.
- Do not claim causation.
- Be concise.
- Maximum 100 words.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

# -----------------------------------------------------
# AUTO CHART
# -----------------------------------------------------
def build_chart(df, question):

    chart_cols = [
        col for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
    ]

    if len(chart_cols) == 0:
        return None

    value_col = chart_cols[0]
    fig = None

    # ---------------------------
    # TIME SERIES
    # ---------------------------

    if "month" in df.columns:

        fig = px.line(
            df,
            x="month",
            y=value_col,
            markers=True,
            title=question
        )



# -----------------------------------------------------
# SINGLE RESULT
# -----------------------------------------------------

    elif len(df) == 1:

        category_col = df.columns[0]

        fig = px.bar(
            df,
            x=category_col,
            y=value_col,
            title=question,
            text=value_col
        )

        fig.update_traces(
            textposition="outside"
        )

    # -----------------------------------------------------
    # SMALL CATEGORY DISTRIBUTION
    # -----------------------------------------------------

    elif (
        len(df.columns) == 2
        and len(df) > 1
        and len(df) <= 6
    ):

        category_col = df.columns[0]

        fig = px.pie(
            df,
            names=category_col,
            values=value_col,
            title=question
        )

    # -----------------------------------------------------
    # CATEGORY RANKING
    # -----------------------------------------------------

    elif len(df.columns) == 2:

        category_col = df.columns[0]

        chart_df = df.sort_values(
            value_col,
            ascending=True
        )

        fig = px.bar(
            chart_df,
            x=value_col,
            y=category_col,
            orientation="h",
            title=question,
            text=value_col
        )

        fig.update_traces(
            textposition="outside"
        )

    # -----------------------------------------------------
    # MULTI-COLUMN RESULT
    # -----------------------------------------------------

    else:

        fig = px.bar(
            df,
            x=df.columns[0],
            y=value_col,
            title=question
        )

    if fig:

        fig.update_layout(
            height=500,
            xaxis_title=None,
            yaxis_title=None
        )

    return fig
# =========================================================
# APPLICATION TABS
# =========================================================

dashboard_tab, ask_tab = st.tabs(
    [
        "📊 Dashboard",
        "🤖 Ask DataSage"
    ]
)


# =========================================================
# DASHBOARD
# =========================================================

with dashboard_tab:

    st.title("📊 DataSage")

    st.caption(
        "Global ChatGPT usage analytics powered by SQLite, "
        "Groq and interactive visualizations."
    )

    inspector = inspect(engine)

    tables = inspector.get_table_names()

    # -----------------------------------------------------
    # KPI CARDS
    # -----------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Database Tables",
        len(tables)
    )

    # Count countries
    try:

        country_df = pd.read_sql(
            """
            SELECT COUNT(DISTINCT country) AS count
            FROM share_of_messages_by_topic_country_month
            """,
            engine
        )

        country_count = int(
            country_df["count"].iloc[0]
        )

    except Exception:

        country_count = 0

    col2.metric(
        "Countries",
        country_count
    )

    # Count age groups
    try:

        age_df = pd.read_sql(
            """
            SELECT COUNT(DISTINCT age_group) AS count
            FROM share_of_messages_by_age_group_month
            """,
            engine
        )

        age_count = int(
            age_df["count"].iloc[0]
        )

    except Exception:

        age_count = 0

    col3.metric(
        "Age Groups",
        age_count
    )

    # Count topics
    try:

        topic_count_df = pd.read_sql(
            """
            SELECT COUNT(DISTINCT topic) AS count
            FROM share_of_messages_by_topic_month
            """,
            engine
        )

        topic_count = int(
            topic_count_df["count"].iloc[0]
        )

    except Exception:

        topic_count = 0

    col4.metric(
        "Topics",
        topic_count
    )

    st.divider()

    # -----------------------------------------------------
    # TOP TOPICS
    # -----------------------------------------------------

    st.subheader("📌 Most Popular Topics")

    try:

        topic_df = pd.read_sql(
            """
            SELECT
                topic,
                AVG(share_of_messages) AS share
            FROM share_of_messages_by_topic_month
            GROUP BY topic
            ORDER BY share DESC
            """,
            engine
        )

        fig = px.bar(
            topic_df.sort_values(
                "share",
                ascending=True
            ),
            x="share",
            y="topic",
            orientation="h",
            title="Average Share of Messages by Topic"
        )

        fig.update_layout(
            height=450,
            xaxis_title="Average Share",
            yaxis_title=""
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    except Exception as e:

        st.warning(
            f"Could not load topic analysis: {e}"
        )

    # -----------------------------------------------------
    # AGE GROUP ANALYSIS
    # -----------------------------------------------------

    st.subheader("👥 Usage by Age Group")

    try:

        age_usage_df = pd.read_sql(
            """
            SELECT
                age_group,
                AVG(share_of_messages) AS share
            FROM share_of_messages_by_age_group_month
            GROUP BY age_group
            ORDER BY share DESC
            """,
            engine
        )

        fig = px.bar(
            age_usage_df.sort_values(
                "share",
                ascending=True
            ),
            x="share",
            y="age_group",
            orientation="h",
            title="Average Share of Messages by Age Group"
        )

        fig.update_layout(
            height=400,
            xaxis_title="Average Share",
            yaxis_title=""
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    except Exception as e:

        st.warning(
            f"Could not load age analysis: {e}"
        )

    # -----------------------------------------------------
    # WORK VS NON-WORK
    # -----------------------------------------------------

    st.subheader("💼 Work vs Non-Work Usage")

    try:

        work_df = pd.read_sql(
            """
            SELECT
                work_related,
                AVG(share_of_messages) AS share
            FROM share_of_messages_by_work_related_month
            GROUP BY work_related
            ORDER BY share DESC
            """,
            engine
        )

        fig = px.pie(
            work_df,
            names="work_related",
            values="share",
            title="Work-Related vs Non-Work-Related Usage"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    except Exception as e:

        st.warning(
            f"Could not load work analysis: {e}"
        )


# =========================================================
# ASK DATASAGE
# =========================================================

with ask_tab:

    st.title("🤖 Ask DataSage")

    st.markdown(
        """
        Ask questions about global ChatGPT usage trends.

        **Examples**

        - Which age group uses ChatGPT the most?
        - What are the top discussion topics?
        - What topics are popular among teenagers?
        - What topics are popular in India?
        - Compare India and the United States.
        - Compare feminine and masculine users.
        - How do people use ChatGPT: asking, doing, or expressing?
        - Is ChatGPT used more for work or non-work purposes?
        """
    )

    question = st.text_input(
        "Ask DataSage",
        placeholder="Which age group uses ChatGPT the most?"
    )

    if st.button(
        "🚀 Generate Insights",
        type="primary"
    ):

        if not question.strip():

            st.warning(
                "Please enter a question."
            )

            st.stop()

        try:

            # -------------------------------------------------
            # GENERATE SQL
            # -------------------------------------------------

            with st.spinner(
                "DataSage is generating SQL..."
            ):

                sql_query = generate_sql(
                    question
                )

            st.subheader(
                "🔍 Generated SQL"
            )

            st.code(
                sql_query,
                language="sql"
            )

            # -------------------------------------------------
            # SQL SECURITY
            # -------------------------------------------------

            is_safe, message = validate_sql(
                sql_query
            )

            if not is_safe:

                st.error(
                    f"🛡️ Query blocked: {message}"
                )

                st.stop()

            # -------------------------------------------------
            # EXECUTE QUERY
            # -------------------------------------------------

            with st.spinner(
                "Running query..."
            ):

                df = pd.read_sql(
                    sql_query,
                    engine
                )

            # -------------------------------------------------
            # EMPTY RESULT
            # -------------------------------------------------

            if df.empty:

                st.warning(
                    "The query executed successfully, "
                    "but no results were found."
                )

                st.stop()

            # -------------------------------------------------
            # QUERY HISTORY
            # -------------------------------------------------

            st.session_state.history.insert(
                0,
                question
            )

            st.session_state.history = (
                st.session_state.history[:10]
            )

            # -------------------------------------------------
            # RESULTS
            # -------------------------------------------------

            st.subheader(
                "📋 Results"
            )

            st.write(
                f"Rows Returned: {len(df)}"
            )

            st.dataframe(
                df,
                use_container_width=True
            )

            # -------------------------------------------------
            # DOWNLOAD
            # -------------------------------------------------

            st.download_button(
                "📥 Download CSV",
                df.to_csv(index=False),
                file_name="datasage_results.csv",
                mime="text/csv"
            )

            # -------------------------------------------------
            # CHART
            # -------------------------------------------------

            st.subheader(
                "📈 Visualization"
            )

            try:

                fig = build_chart(
                    df,
                    question
                )

                if fig:

                    st.plotly_chart(
                        fig,
                        use_container_width=True
                    )

                else:

                    st.info(
                        "No suitable visualization "
                        "could be generated for these results."
                    )

            except Exception as e:

                st.warning(
                    f"Could not generate chart: {e}"
                )

            # -------------------------------------------------
            # AI INSIGHTS
            # -------------------------------------------------

            st.subheader(
                "🧠 AI Insights"
            )

            try:

                with st.spinner(
                    "Analyzing results..."
                ):

                    insight = generate_insight(
                        question,
                        df
                    )

                st.info(
                    insight
                )

            except Exception as e:

                st.warning(
                    f"Could not generate AI insights: {e}"
                )

        except Exception as e:

            st.error(
                f"❌ Error: {e}"
            )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("⚙️ DataSage")

    st.subheader(
        "Database Information"
    )

    inspector = inspect(engine)

    tables = inspector.get_table_names()

    st.metric(
        "Tables",
        len(tables)
    )

    st.write(
        "**Available Tables**"
    )

    for table in tables:

        st.write(
            f"• `{table}`"
        )

    st.divider()

    # -----------------------------------------------------
    # SCHEMA
    # -----------------------------------------------------

    with st.expander(
        "🗂️ View Schema"
    ):

        st.text(
            schema
        )

    # -----------------------------------------------------
    # METADATA
    # -----------------------------------------------------

    with st.expander(
        "📚 View Metadata"
    ):

        st.text(
            metadata
        )

    st.divider()

    # -----------------------------------------------------
    # SQL DEBUGGER
    # -----------------------------------------------------

    st.subheader(
        "🛠️ SQL Debugger"
    )

    sql = st.text_area(
        "Run SQL",
        height=150,
        placeholder="SELECT * FROM table_name LIMIT 10"
    )

    if st.button(
        "▶️ Execute SQL"
    ):

        if not sql.strip():

            st.warning(
                "Enter a SQL query first."
            )

        else:

            try:

                is_safe, message = validate_sql(
                    sql
                )

                if not is_safe:

                    st.error(
                        f"🛡️ Query blocked: {message}"
                    )

                else:

                    # Add LIMIT for safety
                    safe_sql = sql.strip()

                    if (
                        "LIMIT" not in
                        safe_sql.upper()
                    ):

                        safe_sql += " LIMIT 100"

                    debug_df = pd.read_sql(
                        safe_sql,
                        engine
                    )

                    st.dataframe(
                        debug_df,
                        use_container_width=True
                    )

            except Exception as e:

                st.error(
                    f"SQL Error: {e}"
                )

    st.divider()

    # -----------------------------------------------------
    # QUERY HISTORY
    # -----------------------------------------------------

    st.subheader(
        "🕒 Recent Queries"
    )

    if st.session_state.history:

        for q in st.session_state.history:

            st.write(
                f"• {q}"
            )

    else:

        st.caption(
            "No queries yet."
        )