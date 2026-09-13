import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from streamlit_gsheets import GSheetsConnection

REQUIRED_COLUMNS_LEADERBOARD = ["participant", "accuracy", "submission_time", "batch"]


def _open_spreadsheet():
    creds_dict = dict(st.secrets["connections"]["gsheets"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    return client.open_by_url(creds_dict["spreadsheet"])


@st.cache_resource
def get_gsheet_connection():
    return st.connection("gsheets", type=GSheetsConnection)


def ensure_batch_sheet_exists(batch: str, conn):

    try:
        conn.read(worksheet=batch, ttl=0)
        return

    except WorksheetNotFound:
        sh = _open_spreadsheet()

        sh.add_worksheet(
            title=batch,
            rows="1000",
            cols="10",
        )

        empty_df = pd.DataFrame(columns=REQUIRED_COLUMNS_LEADERBOARD)
        conn.update(worksheet=batch, data=empty_df)
    except Exception:
        st.error(
            "An error occured while connecting to Google Sheets. Please wait a moment and try again. (Detail: Could not ensure batch sheet exists.)",
        )
        st.stop()


def ensure_sheet_structure(batch: str, conn):
    try:
        df = conn.read(worksheet=batch, ttl=0)

        if df is None or df.empty:
            empty_df = pd.DataFrame(columns=REQUIRED_COLUMNS_LEADERBOARD)
            conn.update(worksheet=batch, data=empty_df)

            return empty_df

        return df

    except Exception:
        st.error(
            "An error occured while connecting to Google Sheets. Please wait a moment and try again. (Detail: Could not ensure batch sheet structure.)",
        )
        st.stop()


@st.cache_data
def configure_gsheet(batch: str | None = None, _store=None):
    try:
        "connections" in st.secrets
    except Exception:
        return "Streamlit secrets not found or empty. Please set up your secrets as per the instructions."

    if (
        "connections" in st.secrets
        and "gsheets" in st.secrets["connections"]
        and "spreadsheet" in st.secrets["connections"]["gsheets"]
        and "private_key" in st.secrets["connections"]["gsheets"]
    ):
        try:
            _store["gsheet_conn"] = get_gsheet_connection()

            if batch and batch not in _store["configured_batches"]:
                ensure_batch_sheet_exists(batch, _store["gsheet_conn"])
                ensure_sheet_structure(batch, _store["gsheet_conn"])
                _store["configured_batches"].add(batch)
            return "Successful"
        except Exception:
            st.error(
                "Error connecting to Google Sheets. Please check the settings or try again later.",
            )
    else:
        return "Streamlit secrets incomplete."
