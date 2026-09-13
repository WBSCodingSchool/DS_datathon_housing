import io

import pandas as pd
import streamlit as st


def get_ready_test(RESULTS_PATH: str, uploaded_file):
    """Prepare the test DataFrame by validating the uploaded file and renaming its columns.

    Args:
        RESULTS_PATH (str): Path to the results file.
        uploaded_file: Streamlit uploaded file object.

    Returns:
        pd.DataFrame: Prepared test DataFrame.

    """
    results = pd.read_csv(RESULTS_PATH)
    results.columns = ["id", "real"]

    test = pd.read_csv(io.StringIO(uploaded_file.read().decode("utf-8")))

    if test.columns.to_list() != ["Id", "Expensive"]:
        st.error('Column names must match "Id" and "Expensive" - case sensitive!')
        return 0
    if test.shape != results.shape:
        st.error("Your file should contain 1459 rows and 2 columns")
        return 0
    if test.Expensive.unique().tolist() not in [[0, 1], [1, 0], [1], [0]]:
        st.error("Predictions should only have values of 0 and 1")
        return 0
    if (test.Id == results.id).sum() != 1459:
        st.error(
            "Your Id column might be wrong or mixed up. You should have same Id's as the test file. Order of Id's should also be the same.",
        )
        return 0

    test.columns = ["id", "preds"]
    return test.astype("int32")


def get_accuracy(RESULTS_PATH: str, test: pd.DataFrame):
    """Calculate the accuracy of the test predictions and return a DataFrame with participant results.

    Args:
        RESULTS_PATH (str): Path to the results file.
        test (pd.DataFrame): Test DataFrame.

    Returns:
        pd.DataFrame: DataFrame with participant results.

    """
    results = pd.read_csv(RESULTS_PATH)
    results.columns = ["id", "real"]
    results = results.astype("int32")
    accuracy_count = (
        results.merge(test, how="left", on="id")
        .assign(check=lambda df_: df_["real"] == df_["preds"])["check"]
        .sum()
    )
    accuracy_value = accuracy_count / results.shape[0]

    return pd.DataFrame(
        [
            [
                accuracy_value,
                st.session_state.user_name,
                st.session_state.batch,
                pd.Timestamp.now().isoformat(),
            ],
        ],
        columns=["accuracy", "participant", "batch", "submission_time"],
        index=["result"],
    ), results
