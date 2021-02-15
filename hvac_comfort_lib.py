import os
import re
import pandas as pd
from pandas import ExcelWriter
import numpy as np
import plotly
import plotly.offline as pyo
import plotly.graph_objs as go
import plotly.figure_factory as ff

def read_config(filepath):
    df = pd.read_excel(filepath)
    return df

def get_val(df, var):
    value = df.loc[df["Parameter"]==var, "Value"].values[0]
    return value

def get_values(df, var):
    value = df.loc[df["Parameter"]==var, "Value"].values[0]

    # Split string into list of multiple values
    values = [x.strip() for x in value.split(',')]
    return values

def save_xls(list_dfs, xls_path):
    with ExcelWriter(xls_path) as writer:
        for n, df in enumerate(list_dfs):
            sheetname = "sheet{}".format(n)
            df.to_excel(writer, sheetname)
        writer.save()

def get_label_mapping(filepath, sheetname):
    # Create data label mapping dict from spreadsheet
    label_mapping = pd.read_excel(filepath, sheetname)
    label_mapping = label_mapping.set_index("Southern_Labels")
    label_mapping = label_mapping.to_dict()["Model_Labels"]
    return label_mapping

def init_HTML(filepath):
    HTML = open(filepath, "w")
    HTML.write("<html>\n<head></head>\n<body>\n")
    return HTML


def import_hvac(filepath, label_mapping):
    # Read CSV
    df = pd.read_csv(filepath)

    # Remove null columns
    df = df.dropna(axis = 1, how = 'all')

    # Remove the ".1" from the end of column names
    df = df.rename(columns=lambda x: re.sub('\.1','',x))

    df = df.loc[:,~df.columns.duplicated()]

    # Rename columns according to label mapping
    df = df.rename(columns=label_mapping)

    # Drop Columns witn no column name
    df = df.loc[:, df.columns.notnull()]

    # Remove columns not in the label_mapping dict
    df = df.filter(items = list(label_mapping.values()))

    # Convert UTC times to US/Central
    df = localize_time(df)

    return df

def localize_time(df, tz1="UTC", tz2="US/Central"):
    # Converts from "Timestamp" column from tz1(UTC) to tz2(US/Central)
    df["Timestamp"] = pd.to_datetime(df.Timestamp)
    df["Timestamp"] = df["Timestamp"].dt.tz_localize("UTC") # Add UTC timezone
    df["Timestamp"] = df["Timestamp"].dt.tz_convert("US/Central").dt.tz_localize(None) # Convert to Central, then drop tz.

    return df
def get_comfortband_counts(df, zone_num):
    """
    Calculates the number of timesteps that each temperature is within the comfort
    band as determined by the range between the heating and cooling setpoints.
    Args:
        df: dataframe containing "heat_sp_{}" and "cool_sp_{}" where {} is the
            zone number specified by zone_num
        zone_num: the zone number specifying which heating and cooling setpoints
            to count.
    Returns:
        df_comfort: pandas series with index of each temperature and value
            for the count of timesteps from df where the heating and cooling
            setpoint-specified-comfortband encompasses the given temperature

    """
    heatLabel = "heat_sp_{}".format(zone_num)
    coolLabel = "cool_sp_{}".format(zone_num)

    if (heatLabel in df) & (coolLabel in df):
        df_comfort = pd.DataFrame(columns = np.arange(df[heatLabel].min(), df[coolLabel].max()+1))
    else:
        return None

    for sp in df_comfort:
        df_comfort[sp] = ((df[heatLabel] <= sp) & (df[coolLabel] >= sp))

    # Aggregate over time
    df_comfort = df_comfort.sum()

    return df_comfort

def get_off_counts(df, zone):

    df = df[df.op_mode == "Off"]

    df = df.filter(regex="rm_temp")

    df.columns = df.columns.map(lambda x: "off_" + x)

    for zone in df:

        zone_valcounts = df[zone].value_counts()
        if "merged" not in locals():
            merged = zone_valcounts
        else:
            merged = pd.concat([merged, zone_valcounts], axis=1)

    return merged


def get_rm_temp_counts(df):
    df = df.filter(regex="rm_temp")

    for zone in df:
        zone_valcounts = df[zone].value_counts()

        if "merged" not in locals():
            merged = zone_valcounts
        else:
            merged = pd.concat([merged, zone_valcounts], axis=1)

    return merged

def calculate_temp_1090(df):
    """
    For a dataframe (df) with rm_temp_{} columns and op_mode column
    Calculates the 10th and 90th percentile for each rm_temp_{} column as
    well as the 10th and 90th percentile for each tm_temp_{} columns when
    op_mode is "Off"

    Returns data frame indexed to rm_temp and columns for each 10th and 90th percentile
    rt_10p_{}
    rt_90p_{}
    rt_off_10p_{}
    rt_off_90p_{}
    """
    output = pd.DataFrame(index = [0])

    df_off = df[df.op_mode == "Off"]

    #for zone in range(0,max_nZones):
    for rt_col in [col for col in df.columns if "rm_temp" in col]:
        zone = rt_col.split("_")[-1]
        output["rt_10p_{}".format(zone)] = df[rt_col].quantile(0.1)
        output["rt_90p_{}".format(zone)] = df[rt_col].quantile(0.9)
        output["rt_off_10p_{}".format(zone)] = df_off[rt_col].quantile(0.1)
        output["rt_off_90p_{}".format(zone)] = df_off[rt_col].quantile(0.9)

    output["start_date"] = df["Timestamp"].iloc[0]
    output["end_date"] = df["Timestamp"].iloc[-1]
    return output

def plot_comfband_bars(df, savepath, fig_title):
    """
    Plots bar chart for the counts of each setpoint within the comfortband
    """

    for zone in df:


        if type(zone) == int:
            label = "Zone {} SP".format(zone)
            continue
        elif "norm" in zone:
            continue
        elif "off_rm_temp" in zone:
            z = zone.split("_")[-1]
            label = "Z{} Off Counts".format(z)
        elif "rm_temp" in zone:
            continue # This is to ignore off counts 
            z = zone.split("_")[-1]
            label = "Z{} Rm Temp Counts".format(z)

        trace = go.Bar(
                x = df.index,
                y = df[zone],
                name = label
        )

        if "data" not in locals():
            data = [trace]
        else:
            data.append(trace)

    layout = go.Layout(
            title = fig_title,
            yaxis = dict(title="Number of Timesteps"),
            xaxis = dict(
                    title="Room Temperature [deg F]",
                    range = [60, 80]
            ),
            boxmode="group"
    )

    fig = go.Figure(data=data, layout=layout)
    pyo.plot(fig, filename = savepath, auto_open=False)
    return
