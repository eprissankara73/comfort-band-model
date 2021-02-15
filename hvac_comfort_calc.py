

import hvac_comfort_lib as lib
import pandas as pd

############################################
# Get Run Configuration 
config_filepath = "./HVAC_Comfort_Config.xlsx"
config = pd.read_excel(config_filepath)

label_mapping_file = lib.get_val(config, "Label Mapping Filepath")
label_mapping_sheetname = lib.get_val(config, "Label Mapping Sheetname") 
dir_in = lib.get_val(config, "Model Input Data Dir")
results_dir = lib.get_val(config, "Model Output Dir")
dir_subplots = results_dir + lib.get_val(config, "Subplots Dir")
rlids = lib.get_values(config, "RLIDs")
max_nZones = lib.get_val(config, "Maximum Number of Zones")
comfband_filepath = results_dir + lib.get_val(config, "Results Plots Filename")
comf1090_filepath = results_dir + lib.get_val(config, "Results Filename")
months = lib.get_values(config, "Months")

############################################

# Import Label Mapping 
label_mapping = lib.get_label_mapping(label_mapping_file, label_mapping_sheetname) 

# Create Results DataFrames List 
all_comfbands = []

################################################
# Plot frequency of occurency of room temperatres and setpoint ranges

# Create Output HTML File 
HTML_comfband = lib.init_HTML(comfband_filepath) 

#HTML_comfband = open(comfband_filepath, "w")
#HTML_comfband.write("<html>\n<head></head>\n<body>\n")

for rlid in rlids:
    print("Plotting Comfortband: {}".format(rlid))

    for month in months:

        hvac_filepath = "{}{}_hvac_{}.csv".format(dir_in, rlid, month)

        df = lib.import_hvac(hvac_filepath, label_mapping)

        comfband_counts = []
        off_counts = []
        for zone in range(0, max_nZones):
            comfband_counts.append(lib.get_comfortband_counts(df,zone))

        off_counts.append(lib.get_off_counts(df,zone))

        comfband_counts = pd.concat(comfband_counts, axis=1)

        rm_temp_counts = lib.get_rm_temp_counts(df)

        comfband_counts = comfband_counts.join(rm_temp_counts)
        comfband_counts = comfband_counts.join(off_counts)

        df_1090 = lib.calculate_temp_1090(df)
        df_1090["RLID"] = rlid

        if "df_1090s" not in globals():
            df_1090s = df_1090
        else:
            df_1090s = pd.concat([df_1090s, df_1090])



        for zone in range(0, max_nZones):
            if zone in comfband_counts:
                comfband_counts["norm_off_rm_temp_{}".format(zone)] = comfband_counts["off_rm_temp_{}".format(zone)]/comfband_counts["rm_temp_{}".format(zone)]

        savepath = "{}{}_comfbands_{}.html".format(dir_subplots, rlid, month)
        fig_title = "{}: {}".format(rlid, month)
        lib.plot_comfband_bars(comfband_counts, savepath, fig_title)

        # Update HTML File
        HTML_comfband.write('<object data="{}" width="100%" height="400"></object>\n'.format(savepath))

    all_comfbands.append(df_1090s.reset_index(drop=True))
    del df_1090s

HTML_comfband.write("</body>\n</html>")

HTML_comfband.close()


# Export Comfort Band Stats to Excel
lib.save_xls(all_comfbands, comf1090_filepath)
