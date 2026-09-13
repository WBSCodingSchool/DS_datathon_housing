import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from src.gsheet import configure_gsheet
from src.utils import (
    build_leaderboards,
    get_global_store,
)


CLASS_NAMES = ["Non-Expensive", "Expensive"]


def get_participant_info():
    store = get_global_store()

    if (
        st.session_state.user_name
        and st.session_state.code_input
        and st.session_state.batch
    ):
        if st.session_state.batch not in store["submissions"]:
            try:
                configure_gsheet(st.session_state.batch, _store=store)
                if st.session_state.batch not in store["submissions"]:
                    store["submissions"][st.session_state.batch] = store[
                        "gsheet_conn"
                    ].read(
                        worksheet=st.session_state.batch,
                        ttl=0,
                    )
                    build_leaderboards()
            except Exception:
                st.error(
                    "An error occured while connecting to Google Sheets. Please wait a moment and try again. (Detail: Could not load your batch submissions.)",
                )
                st.stop()

        st.info(f"Welcome {st.session_state.user_name} from {st.session_state.batch}")

    else:
        st.write(
            "If you haven't done so yet, please download the test data, train data, and an example upload file below.",
        )

        cols = st.columns(4)

        with cols[0], open("data/housing-classification-iter6.csv", "rb") as f:
            st.download_button(
                label="Download  \n train data",
                data=f,
                file_name="train.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with cols[1], open("data/test.csv", "rb") as f:
            st.download_button(
                label="Download  \n test data",
                data=f,
                file_name="test.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with cols[2], open("data/data_description.txt", "rb") as f:
            st.download_button(
                label="Download  \n data description",
                data=f,
                file_name="data_description.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with cols[3], open("data/example_upload.csv", "rb") as f:
            st.download_button(
                label="Download  \n example upload",
                data=f,
                file_name="example_upload.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.divider()

        st.warning(
            "Please enter **your name** (real or alias) and **the code** provided by your instructor.",
        )

        batches_df = store["batches"]

        user_name = st.text_input("Enter your name: ")
        if user_name:
            st.session_state.user_name = user_name

        code_input = st.text_input("Enter your batch's secret code: ", type="password")
        if code_input:
            st.session_state.code_input = code_input
            code_to_batch = batches_df.set_index("Code")["Batch"]
            st.session_state.batch = code_to_batch.get(
                st.session_state.code_input,
                st.session_state.get("batch"),
            )
            code_to_alltime = (
                batches_df.set_index("Code")["Show All-time?"]
                .fillna(False)
            )
            st.session_state.alltime = code_to_alltime.get(st.session_state.code_input)

        if (
            st.session_state.user_name
            and st.session_state.code_input
            and st.session_state.batch
        ):
            st.rerun()


def plot_submissions(participant_name):
    """Plot submission accuracy for a participant over time.

    Args:
        participant_name (str): Name of the participant.

    """
    store = get_global_store()
    participant_submissions = (
        store["submissions"][st.session_state.batch]
        .query("participant == @participant_name")
        .filter(["submission_time", "accuracy"])
        .copy()
    )
    if len(participant_submissions) > 1:
        participant_submissions["submission_time"] = pd.to_datetime(
            participant_submissions["submission_time"],
            format="ISO8601",
        )
        participant_submissions = participant_submissions.sort_values(
            "submission_time",
        ).set_index("submission_time")
        st.line_chart(participant_submissions)
    elif len(participant_submissions):
        st.success("Congratulations on your first submission!")


@st.fragment(run_every=10)
def display_leaderboard() -> None:
    if st.session_state.batch == "anonymous":
        st.write("You decided to not compete in any leaderboard.")
    else:
        store = get_global_store()
        st.divider()
        st.header(f"🏆 Leaderboard from {st.session_state.batch}", anchor=False)
        submissions_df = store["submissions"][st.session_state.batch]
        if not submissions_df.empty:
            leaderboard_df = store["leaderboards"][st.session_state.batch].drop(
                "batch",
                axis=1,
            )
            st.dataframe(leaderboard_df)
        else:
            st.write("There are no submissions from your batch yet.")

        st.session_state["manual_refresh"] = False
        if st.button("Refresh leaderboard(s)"):
            st.session_state["manual_refresh"] = True
            st.rerun()

        if (not store["alltime_submissions"].empty) and st.session_state.alltime:
            st.divider()
            st.header("👑 All-time Leaderboard", anchor=False)

            st.dataframe(store["alltime_leaderboard"])


def display_participant_results(participant_results, predictions, labels) -> None:
    st.header("📊 Your results", anchor=False)
    st.success(f"Success! Model Accuracy: {participant_results['accuracy'].values[0]:.2%}")
    fig, ax = plt.subplots(figsize=(2, 2), facecolor="black")
    df = predictions.merge(
        labels,
        on="id",
    )
    cm = pd.crosstab(
        pd.Series(df["real"].values, name="Actual"),
        pd.Series(df["preds"].values, name="Predicted"),
    )
    cm = cm.reindex(
        index=range(len(CLASS_NAMES)),
        columns=range(len(CLASS_NAMES)),
        fill_value=0,
    )
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="copper",
        xticklabels=CLASS_NAMES,
        yticklabels=CLASS_NAMES,
        ax=ax,
        cbar=False,
        annot_kws={"color": "white", "fontsize": 8},
    )
    ax.set_xlabel("Predicted", color="white", fontsize=8)
    ax.set_ylabel("True Label", color="white", fontsize=8)
    ax.tick_params(colors="white", labelsize=6, which="both", length=0)
    ax.tick_params(axis="x", rotation=0, colors="white")
    st.pyplot(fig, use_container_width=False)
    plt.close(fig)


def display_setup_error(error_desc: str) -> None:
    st.warning("⚠️ **Leaderboard Configuration Missing**")
    st.info(f"""
        It looks like this app hasn't been connected to a Google Sheet yet.
    
        Error details: {error_desc}
    """)


def display_admin():
    """Admin tools for instructors to clear global cache."""
    st.divider()
    st.subheader("🛠️ Instructor Settings")
    if st.button("Clear Global Cache"):
        get_global_store.clear()
        configure_gsheet.clear()
        st.rerun()
