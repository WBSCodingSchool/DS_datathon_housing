import streamlit as st

from src.display import (
    display_admin,
    display_leaderboard,
    display_participant_results,
    get_participant_info,
    plot_submissions,
)
from src.utils import process_uploaded_file, state_inits, update_submissions

# Constants
RESULTS_PATH = "data/true_y.csv"


def main():
    st.title("Welcome to our classification competition!", anchor=False)

    if st.session_state.get("batch") == "Instructor":
        display_admin()

    get_participant_info()

    if st.session_state.user_name and st.session_state.batch:

        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        if uploaded_file and not st.session_state.get("manual_refresh", False):
            result = process_uploaded_file(uploaded_file, RESULTS_PATH)
            if result is None:
                st.stop()
            else:
                participant_results, predictions, labels = result
            display_participant_results(participant_results, predictions, labels)
            update_submissions(participant_results)
        else:
            st.warning("Please upload a file.")

        plot_submissions(st.session_state.user_name)
        display_leaderboard()


state_inits()
main()
