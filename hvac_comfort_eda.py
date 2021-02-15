# -*- coding: utf-8 -*-
"""
Created on Fri Jun 14 19:58:01 2019

@author: pcsh009
"""

import os
import re
import pandas as pd
from pandas import ExcelWriter
import numpy as np
import plotly
import plotly.offline as pyo
import plotly.graph_objs as go
import plotly.figure_factory as ff

label_mapping_file = "../data_label_mapping.xlsx"
label_mapping_sheet = "HVAC" 

# Create data label mapping dict from spreadsheet
label_mapping = pd.read_excel(label_mapping_file, label_mapping_sheet)
label_mapping = label_mapping.set_index("Southern_Labels")
label_mapping = label_mapping.to_dict()["Model_Labels"]

def save_xls(list_dfs, xls_path):
    with ExcelWriter(xls_path) as writer:
        for n, df in enumerate(list_dfs):
            sheetname = "sheet{}".format(n)
            df.to_excel(writer, sheetname)
        writer.save()

def drop_keys_from_dict(D, string):
    D_new = {k: D[k] for k in D if not k.startswith(string)}
    return D_new


def localize_time(df, tz1="UTC", tz2="US/Central"):
    # Converts from "Timestamp" column from tz1(UTC) to tz2(US/Central)
    df["Timestamp"] = pd.to_datetime(df.Timestamp)
    df["Timestamp"] = df["Timestamp"].dt.tz_localize("UTC") # Add UTC timezone
    df["Timestamp"] = df["Timestamp"].dt.tz_convert("US/Central").dt.tz_localize(None) # Convert to Central, then drop tz.

    return df

def import_hvac_OLD(filepath, label_mapping):
    label_mapping_z2 = label_mapping
    label_mapping_z1 = drop_keys_from_dict(label_mapping_z2, "Zone2")
    label_mapping_z0 = drop_keys_from_dict(label_mapping_z1, "Zone1")

    df = pd.read_csv(filepath)

    # Remove null columns
    df = df.dropna(axis = 1, how = 'all')

    # Remove the ".1" from the end of column names
    df = df.rename(columns=lambda x: re.sub('\.1','',x))

    df = df.rename(columns=label_mapping)



    #df = df[list(label_mapping.values())]
    df = df.loc[:, df.columns.notnull()]
    df = df.filter(items = list(label_mapping.values()))

    df = df.loc[:, df.columns.notnull()]

    df = localize_time(df)

    return df

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

def import_min_cons(filepath):
    df = pd.read_csv(filepath)

    rename_dict = {
            "timestamp.cst": "Timestamp",
            "beopt.group": "Group",
            "value": "W"}

    df = df.rename(columns = rename_dict)

    df = df[list(rename_dict.values())]

    df = df[df.Group == "Heating/Cooling"]

    return df

def resample_hvac_15min(df):
    df["Timestamp"] = pd.to_datetime(df.Timestamp)
    df = df.set_index("Timestamp")

    # Resample to 15 min
    df = df.resample("15T").mean().round()#.round()

    return df

def resample_cons_15min(df):
    df["Timestamp"] = pd.to_datetime(df.Timestamp)

    df = df.set_index("Timestamp")

    df = df.resample("15T").mean()
    return df

def plot_zones_vs_W(df, label, xlabel):
    label0 = label + "_0"
    label1 = label + "_1"
    label2 = label + "_2"

    trace0 = go.Box(
            x = df[label0],
            y = df.W,
            name = "Zone 0"
    )

    data = [trace0]

    if label1 in df:
        trace1 = go.Box(
                x = df[label1],
                y = df.W,
                name = "Zone 1"
        )
        data.append(trace1)

    if label2 in df:
        trace2 = go.Box(
                x = df[label2],
                y = df.W,
                name = "Zone2"
        )
        data.append(trace2)

    layout = go.Layout(
            title = "{}: {}".format(rlid, month),
            yaxis = dict(title="Consumption [W]"),
            xaxis = dict(title=xlabel),
            boxmode="group"
    )

    fig = go.Figure(data = data, layout = layout)
    savepath = "{}{}_{}_box_{}.html".format(dir_subplots, rlid, label, month)
    pyo.plot(fig, filename = savepath, auto_open=False)
    return savepath

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

def calculate_temp_1090(df): 
    """
    For a dataframe (df) with rm_temp_{} columns and op_mode column
    Calculates the 10th and 90th percentile for each rm_temp_{} column as 
    well as the 10th and 90th percentile for each tm_temp_{} columns when 
    op_mode is "Off" 
    
    Returns data frame indexed to rm_temp and columns for each 10th and 90th percentile 
    rm_temp_10th_{} 
    rm_temp_90th_{} 
    off_temp_10th_{} 
    off_temp_90th_{} 
    """ 
    output = pd.DataFrame(index = [0]) 
    
    df_off = df[df.op_mode == "Off"] 
    
    for zone in range(0,max_nZones): 
        if "rm_temp_{}".format(zone) in df: 
            output["rt_10p_{}".format(zone)] = df["rm_temp_{}".format(zone)].quantile(0.1) 
            output["rt_90p_{}".format(zone)] = df["rm_temp_{}".format(zone)].quantile(0.9) 
            output["rt_off_10p_{}".format(zone)] = df_off["rm_temp_{}".format(zone)].quantile(0.1) 
            output["rt_off_90p_{}".format(zone)] = df_off["rm_temp_{}".format(zone)].quantile(0.9) 
        
    output["month"] = month 
    return output 

def plot_comfband_bars(df, savepath):
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
            z = zone.split("_")[-1]
            label = "Z{} Rm Temp Counts".format(z)
        '''
        if type(zone) == int: 
            continue 
        elif "norm" in zone: 
            z = zone.split("_")[-1] 
            label = "Z{} Norm Off Counts".format(z)
        else: 
            continue 
        '''
        
        #elif zone == "op_mode": 
            

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
            title = "{}: {}".format(rlid, month),
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

def get_rm_temp_counts(df):
    df = df.filter(regex="rm_temp")

    for zone in df:
        zone_valcounts = df[zone].value_counts()

        if "merged" not in locals():
            merged = zone_valcounts
        else:
            merged = pd.concat([merged, zone_valcounts], axis=1)

    return merged

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
     

def find_sp_changes(df):

    for mode in ["heat", "cool"]:
        for zone in range(0,max_nZones):
            sp_col = "{}_sp_{}".format(mode, zone)
            rt_col = "rm_temp_{}".format(zone)

            if sp_col not in df:
                continue
            df[sp_col+"_change"] = df[sp_col] - df[sp_col].shift()
            df[sp_col+"_change"] = df[sp_col+"_change"].fillna(0)

            # Replace difference with true/false
            df.loc[df[sp_col+"_change"]!=0, sp_col+"_change"] = True
            df.loc[df[sp_col+"_change"]==0, sp_col+"_change"] = False

            df["is_manual"] = df["ts_mode_{}".format(zone)] == "Manual"

            df[sp_col+"_man_change"] = df[sp_col+"_change"] & df["hold_on"] # & df["is_manual"]

            df[rt_col+"_counter"] = df.groupby((df[rt_col] != df[rt_col].shift(1)).cumsum()).cumcount()
            df[rt_col+"_times"] = False
            df.loc[df[rt_col+"_counter"]==0, rt_col+"_times"] = True

    df["change_flag"] = df[[col for col in df.columns if ("_change" in col) & ("_man" not in col)]].sum(axis=1) != 0

    return df

def count_sp_changes(df, zone_num):
    rt_col = "rm_temp_{}".format(zone_num)
    hsp_col = "heat_sp_{}_man_change".format(zone_num)
    csp_col = "cool_sp_{}_man_change".format(zone_num)
    rt_count_col = rt_col + "_times"

    df_counts = df[[rt_col, hsp_col, csp_col, rt_count_col]].groupby(rt_col).sum()

    df_size = df[rt_col].value_counts()

    df_counts = df_counts.join(df_size)

    df_counts[hsp_col+"_norm"] = df_counts[hsp_col]/df_counts[rt_col]
    df_counts[csp_col+"_norm"] = df_counts[csp_col]/df_counts[rt_col]

    return df_counts

def plot_sp_change_counts(df, savepath):
    for col in df:
        if ("_sp_" not in col) & ("_change" not in col): # & ("rm_temp" not in col):
            continue

        if "rm_temp" in col:
            yaxis = "y2"
        else:
            yaxis = "y"

        bar = go.Bar(
                x = df.index,
                y = df[col],
                name = col,
                yaxis = yaxis,
                opacity = 1
        )

        if "data" not in locals():
            data = [bar]
        else:
            data.append(bar)

    if "_norm" in col:
        ylabel = "Normalized Num of Manual SP Changes"
    else:
        ylabel = "Number of Manual SP Changes"

    layout = go.Layout(
            title = "{}: Zone {}".format(rlid, zone),
            yaxis = dict(title=ylabel),
            yaxis2 = dict(
                    title="Times at room temp",
                    overlaying = "y",
                    side = "right"
            ),
            xaxis = dict(title="Room Temp [deg F]"),
            barmode = "group" #"stack"
    )

    fig = go.Figure(data=data, layout=layout)
    pyo.plot(fig, filename=savepath, auto_open=False)

    return

def plot_rm_temp_freq(df, savepath):
    for col in df:
        if "rm_temp" not in col:
            continue

        bar = go.Bar(
                x = df.index,
                y = df[col],
                name = col,
        )

        if "data" not in locals():
            data = [bar]
        else:
            data.append(bar)

    layout = go.Layout(
            title = "{}: Zone {}".format(rlid, zone),
            yaxis = dict(title="Room Temp Count"),
            xaxis = dict(title="Room Temp [deg F]"),
            barmode="group"
    )

    fig = go.Figure(data=data, layout=layout)
    pyo.plot(fig, filename = savepath, auto_open=False)

    return


def plot_zone_SPs(df, zone_num, savepath):
    # Create Heat Setpoint Trace
    trace_hsp = go.Scatter(
            x = df.index,
            y = df["heat_sp_{}".format(zone_num)],
            opacity = 0.6,
            name = "Z{} Heat SP".format(zone_num)
    )

    # Cool setpoint trace
    trace_csp = go.Scatter(
            x = df.index,
            y = df["cool_sp_{}".format(zone_num)],
            opacity = 0.6,
            name = "Z{} Cool SP".format(zone_num)
    )

    # Room temperature trace
    trace_rmt = go.Scatter(
            x = df.index,
            y = df["rm_temp_{}".format(zone_num)],
            opacity = 0.6,
            name = "Z{} Room Temp".format(zone_num)
    )

    # Hold Status
    trace_hold = go.Scatter(
            x = df.index,
            y = df.hold_on,
            opacity = 0.3,
            name="Hold Enabled",
            yaxis="y2"
    )

    trace_mode = go.Scatter(
            x = df.index,
            y= df.is_manual,
            opacity = 0.3,
            name="Is Manual",
            yaxis="y2"
    )

    trace_change = go.Scatter(
            x = df.index,
            y = df.change_flag,
            opacity = 0.3,
            name = "Change Flag",
            yaxis="y2"
    )


    # Combine traces
    data = [trace_hsp, trace_csp, trace_rmt, trace_hold, trace_mode, trace_change]

    # Define figure layout
    layout = go.Layout(
            title = "{} - Zone {}: Summer".format(rlid, zone_num),
            yaxis = dict(title="Temperature [deg F]"),
            yaxis2 = dict(
                    title="Thermostat Setting (ON/OFF)",
                    overlaying = "y",
                    side = "right"
            ),
            boxmode="group"
    )

    # Plot and save figure
    fig = go.Figure(data = data, layout = layout)
    pyo.plot(fig, filename = savepath, auto_open=False)

    return



# Define Run Parameters 
dir_in = "./Model_Data/"
dir_subplots = "./HTML_Subplots/"
dir_sp_plots = dir_subplots + "SP_Plots/"
dir_sp_changes = dir_subplots + "SP_Change_Counts/"
rlids = ["RL25", "RL29", "RL32", "RL34", "RL44"]
months = ["2018-07", "2018-09", "2018-10", "2018-11", "2019-01", "2019-03"]
max_nZones = 3

# Output Filepaths
comfband_filepath = "./Monthly Comfband Plots.html"
comf1090_filepath = "./Monthly 10-90p Comfband Stats.xlsx" 



################################################
# Plot frequency of occurency of room temperatres and setpoint ranges 


HTML_comfband = open(comfband_filepath, "w") 
HTML_comfband.write("<html>\n<head></head>\n<body>\n") 

all_comfbands = [] 

for rlid in rlids: 
    print("Plotting Comfortband: {}".format(rlid)) 
    
    #for season in [3,4]: 
    for month in months: 
        #month = "season{}".format(season) 
        
        hvac_filepath = "{}{}_hvac_{}.csv".format(dir_in, rlid, month) 
        
        df = import_hvac(hvac_filepath, label_mapping) 
        
        comfband_counts = []
        off_counts = [] 
        for zone in range(0, max_nZones): 
            comfband_counts.append(get_comfortband_counts(df,zone)) 
                
        off_counts.append(get_off_counts(df,zone)) 

        comfband_counts = pd.concat(comfband_counts, axis=1)
            
        rm_temp_counts = get_rm_temp_counts(df) 
        
        comfband_counts = comfband_counts.join(rm_temp_counts) 
        comfband_counts = comfband_counts.join(off_counts) 
        
        df_1090 = calculate_temp_1090(df) 
        df_1090["RLID"] = rlid 
        
        if "df_1090s" not in globals(): 
            df_1090s = df_1090
        else: 
            df_1090s = pd.concat([df_1090s, df_1090]) 
        
        
        
        for zone in range(0, max_nZones): 
            if zone in comfband_counts: 
                comfband_counts["norm_off_rm_temp_{}".format(zone)] = comfband_counts["off_rm_temp_{}".format(zone)]/comfband_counts["rm_temp_{}".format(zone)] 
        
        savepath = "{}{}_comfbands_{}.html".format(dir_subplots, rlid, month)
        plot_comfband_bars(comfband_counts, savepath)

        # Update HTML File
        HTML_comfband.write('<object data="{}" width="100%" height="400"></object>\n'.format(savepath))
        
    all_comfbands.append(df_1090s.reset_index(drop=True)) 
    del df_1090s 
        
HTML_comfband.write("</body>\n</html>")

HTML_comfband.close()


# Export Comfort Band Stats to Excel 
save_xls(all_comfbands, comf1090_filepath) 
        
        
'''


# Plot power draw vs temperature boxplots

# Create HTML Files
HTML_comfband = open("Season3-4 ComfBand Plots.html", "w")
#HTML_coolbox = open("Season3-4 CoolSP Boxplots.html", "w")
#HTML_heatbox = open("Season3-4 HeatSP Boxplots.html", "w")
#HTML_roombox = open("Season3-4 RmTemp BoxPlots.html", "w")

# Write HTML headers
HTML_comfband.write("<html>\n<head></head>\n<body>\n")
#HTML_coolbox.write("<html>\n<head></head>\n<body>\n")
#HTML_heatbox.write("<html>\n<head></head>\n<body>\n")
#HTML_roombox.write("<html>\n<head></head>\n<body>\n")

for rlid in rlids:
    print("Plotting {} Comfortband".format(rlid))
    #for month in months:
    for season in [3,4]:
        month="season{}".format(season)
        hvac_filepath = "{}{}_hvac_{}.csv".format(dir_in, rlid, month)
        cons_filepath = "{}{}_{}.csv".format(dir_in, rlid, month)

        hvac = import_hvac(hvac_filepath, label_mapping)
        hvac = resample_hvac_15min(hvac)

        #cons = import_min_cons(cons_filepath)
        #cons = resample_cons_15min(cons)

        #df = hvac.join(cons)
        df = hvac

        # Plot Boxplots
        #hsp_plot_path = plot_zones_vs_W(df, "heat_sp", "Heat Setpoint [deg F]")
        #csp_plot_path = plot_zones_vs_W(df, "cool_sp", "Cool Setpoint [deg F]")
        #rmt_plot_path = plot_zones_vs_W(df, "rm_temp", "Room Temp [deg F]")

        # Add Current plot to overall HTML files
        #HTML_heatbox.write('<object data="{}" width="100%" height="400"></object>\n'.format(hsp_plot_path))
        #HTML_coolbox.write('<object data="{}" width="100%" height="400"></object>\n'.format(csp_plot_path))
        #HTML_roombox.write('<object data="{}" width="100%" height="400"></object>\n'.format(rmt_plot_path))

        # Get Comfort Bands
        z0_comfortband = get_comfortband_counts(df, 0)
        z1_comfortband = get_comfortband_counts(df, 1)
        z2_comfortband = get_comfortband_counts(df, 2)

        # Get Room Temp Counts
        rm_temp_counts = get_rm_temp_counts(df)

        comfband_counts = pd.concat([z0_comfortband, z1_comfortband, z2_comfortband], axis=1)
        comfband_counts = comfband_counts.join(rm_temp_counts)

        savepath = "{}{}_comfbands_{}.html".format(dir_subplots, rlid, month)
        plot_comfband_bars(comfband_counts, savepath)

        # Update HTML File
        HTML_comfband.write('<object data="{}" width="100%" height="400"></object>\n'.format(savepath))

HTML_comfband.write("</body>\n</html>")
#HTML_coolbox.write("</body>\n</html>")
#HTML_heatbox.write("</body>\n</html>")
#HTML_roombox.write("</body>\n</html>")

HTML_comfband.close()
#HTML_coolbox.close()
#HTML_heatbox.close()
#HTML_roombox.close()

'''

'''

####################################################
# Plot SP change count vs room temp histogram

# Defind Paramters
hvac_filepath_pattern = "{}{}_hvac_season{}.csv"
rlids = ["RL25", "RL29", "RL32", "RL34", "RL44"]

############################################
# Run Comfort band analysis Based on number of manual setpoint changes 

for season in [3,4]:
    # Create HTML File
    HTML_changes = open("All SP Change Bars-Season{}.html".format(season), "w")
    HTML_normchanges = open("All SP NormChange Bars-Season{}.html".format(season), "w")
    HTML_rt_freq = open("All Room Temp Frequency Bars-Season{}.html".format(season), "w")

    HTML_changes.write("<html>\n<head></head>\n<body>\n")
    HTML_normchanges.write("<html>\n<head></head>\n<body>\n")
    HTML_rt_freq.write("<html>\n<head></head>\n<body>\n")


    for rlid in rlids:
        print("Plotting Manual Changes: {}".format(rlid))

        hvac_filepath = hvac_filepath_pattern.format(dir_in, rlid, season)

        df = import_hvac(hvac_filepath, label_mapping)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df = df.set_index("Timestamp")

        df = find_sp_changes(df)

        for zone in range(0,max_nZones):
            if ("heat_sp_{}".format(zone) in df) & ("cool_sp_{}".format(zone) in df):
                plot_zone_SPs(df, zone, "{}{}_Z{}_SP_season{}.html".format(dir_sp_plots, rlid, zone, season))

                zone_counts = count_sp_changes(df, zone)

                changes_savepath = "{}{}_sp{}_season{}_changes.html".format(dir_sp_changes, rlid, zone, season)
                norm_changes_savepath = "{}{}_sp{}_season{}_change_norm.html".format(dir_sp_changes, rlid, zone, season)

                plot_sp_change_counts(zone_counts.iloc[:,:2], changes_savepath)
                plot_sp_change_counts(zone_counts.iloc[:,4:], norm_changes_savepath)

                rm_temp_savepath = "{}{}_rt{}_season{}_freq.html".format(dir_sp_changes, rlid, zone, season)
                plot_rm_temp_freq(zone_counts.iloc[:,2:4], rm_temp_savepath)

                HTML_changes.write('<object data="{}" width="100%" height="400"></object>\n'.format(changes_savepath))
                HTML_normchanges.write('<object data="{}" width="100%" height="400"></object>\n'.format(norm_changes_savepath))
                HTML_rt_freq.write('<object data="{}" width="100%" height="400"></object>\n'.format(rm_temp_savepath))

            else:
                print("Zone {} not in {} data".format(zone, rlid))


    HTML_changes.write("</body>\n</html>")
    HTML_normchanges.write("</body>\n</html>")
    HTML_rt_freq.write("</body>\n</html>")

    HTML_changes.close()
    HTML_normchanges.close()
    HTML_rt_freq.close()
    
    
'''
