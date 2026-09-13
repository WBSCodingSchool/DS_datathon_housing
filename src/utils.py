import io
import logging
import sys

import pandas as pd
import streamlit as st

from src.eval import get_accuracy, get_ready_test
from src.gsheet import configure_gsheet


class CloudLogFormatter(logging.Formatter):
    # ANSI Terminal Palette Codes
    RESET = "\033[0m"
    ORANGE = "\033[33m"
    GREEN = "\033[32m"
    MAX_USER_LENGTH = 10

    def format(self, record):
        level_map = {
            "DEBUG": "DEBUG",
            "INFO": "INFO",
            "WARNING": "WARN",
            "ERROR": "ERROR",
            "CRITICAL": "FATAL",
        }
        raw_user = str(getattr(record, "user", "SYSTEM"))
        user_formatted = (
            raw_user[:self.MAX_USER_LENGTH]
            if len(raw_user) > self.MAX_USER_LENGTH
            else raw_user.ljust(self.MAX_USER_LENGTH)
        )


        asctime = self.formatTime(record, self.datefmt)
        levelname = level_map.get(record.levelname, f"{record.levelname:<5}")
        msg = record.getMessage()

        if "waitlisted" in msg.lower():
            color_prefix = self.ORANGE
        elif "completed" in msg.lower() or "success" in msg.lower():
            color_prefix = self.GREEN
        else:
            color_prefix = ""

        # Assemble the final log stream grid string
        if color_prefix:
            return f"{asctime} {levelname} - {user_formatted} {color_prefix}{msg}{self.RESET}"
        return f"{asctime} {levelname} - {user_formatted} {msg}"

log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(CloudLogFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = [log_handler]


@st.cache_resource
def get_global_store():
    return {
        "submissions": {},
        "alltime_submissions": None,
        "leaderboards": {},
        "alltime_leaderboard": None,
        "batches": None,
        "batches_last_updated": None,
        "gsheet_conn": None,
        "configured_batches": set(),
    }


def state_inits():

    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "code_input" not in st.session_state:
        st.session_state.code_input = None
    if "batch" not in st.session_state:
        st.session_state.batch = None
    if "alltime" not in st.session_state:
        st.session_state.alltime = None

    store = get_global_store()

    if store["gsheet_conn"] is None:
        configure_gsheet(_store=store)

    if st.session_state.alltime and store["alltime_submissions"] is None:
        load_alltime_data(store)

    if (
        store["batches"] is None
        or store["batches_last_updated"] is None
        or (pd.Timestamp.now() - store["batches_last_updated"]).seconds > 300
    ):
        try:
            store["batches"] = store["gsheet_conn"].read(
                worksheet="Batches",
                ttl=0,
            )
            store["batches_last_updated"] = pd.Timestamp.now()
        except Exception:
            st.error(
                "An error occured while connecting to Google Sheets. Please wait a moment and try again. (Detail: Could not load batch list.)",
            )
            st.stop()


def validate_csv_file(file):
    try:
        file.seek(0)  # Reset file pointer to the beginning
        df = pd.read_csv(io.StringIO(file.read().decode("utf-8")))

        if set(["Id", "Expensive"]).issubset(df.columns):
            return True
        return False
    except Exception:
        return False


def update_submissions(participant_results: pd.DataFrame):
    store = get_global_store()
    batch = st.session_state.batch

    if batch in store["submissions"] and not store["submissions"][batch].empty:
        updated_submissions_df = pd.concat(
            [store["submissions"][batch], participant_results],
            ignore_index=True,
        )
    else:
        updated_submissions_df = participant_results

    try:
        store["gsheet_conn"].update(worksheet=batch, data=updated_submissions_df)

        store["submissions"][batch] = updated_submissions_df

        store["alltime_submissions"] = pd.concat(
            [store["alltime_submissions"], participant_results],
            ignore_index=True,
        )
    except Exception:
        st.error(
            "An error occured while submitting your results. Please try again later. (Detail: Could not update submissions in Google Sheets.)",
        )
        st.stop()

    build_leaderboards()


def process_uploaded_file(uploaded_file, RESULTS_PATH: str):
    if validate_csv_file(uploaded_file):
        try:
            uploaded_file.seek(0)  # Reset file pointer to the beginning
            test = get_ready_test(RESULTS_PATH, uploaded_file)
            if isinstance(test, pd.DataFrame):
                participant_results, labels = get_accuracy(RESULTS_PATH, test)
                st.success("Dataframe uploaded successfully!")
                logger.info(
                    f"Evaluation successfull. Accuracy: {participant_results['accuracy'].values[0]:.2%}",
                    extra={"user": st.session_state.user_name, "comp": "UPLOADER"},
                )
                return participant_results, test, labels

        except Exception as e:
            st.error(f"The file could not be processed. Error: {e}")
            return None
    else:
        st.error(
            "The uploaded file has the wrong format. Please, review it and ensure it contains the required columns.",
        )
        return None


def generate_leaderboard_dataframe(submissions_df):
    best_results_per_participant = (
        submissions_df.assign(
            attempts=lambda df_: df_.groupby("participant")["participant"].transform(
                "count",
            ),
        )
        .sort_values(
            ["accuracy", "submission_time", "batch"],
            ascending=[False, True, True],
        )
        .drop_duplicates(subset=["participant"], keep="first")
        .assign(
            rank=lambda df_: df_["accuracy"].rank(
                method="min",
                ascending=False,
            ).astype(int),
        )
        .filter(["rank", "participant", "accuracy", "attempts", "batch"])
    )

    best_results_per_participant["rank"] = best_results_per_participant["rank"].where(
        best_results_per_participant["rank"].ne(
            best_results_per_participant["rank"].shift(),
        ),
        "",
    ).astype(str)

    return best_results_per_participant.set_index("rank")


def build_leaderboards():
    store = get_global_store()

    for batch, df in store["submissions"].items():
        if df is not None and not df.empty:
            store["leaderboards"][batch] = generate_leaderboard_dataframe(df)
        else:
            store["leaderboards"][batch] = pd.DataFrame()

    if (
        store["alltime_submissions"] is not None
        and not store["alltime_submissions"].empty
    ):
        store["alltime_leaderboard"] = generate_leaderboard_dataframe(
            store["alltime_submissions"],
        )


def load_alltime_data(store):
    try:
        batches = (
            store["gsheet_conn"].read(worksheet="Batches", ttl=0)["Batch"].tolist()
        )
        worksheet_titles = [b for b in batches if b not in ["Batches", "anonymous"]]

        dfs = []
        for ws_name in worksheet_titles:
            try:
                df = store["gsheet_conn"].read(worksheet=ws_name, ttl=0)
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception:
                pass

        store["alltime_submissions"] = (
            pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        )
        build_leaderboards()
    except Exception:
        store["alltime_submissions"] = pd.DataFrame()
