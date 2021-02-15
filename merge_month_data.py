# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 16:26:20 2019

@author: pcsh009
"""

import os 
import pandas as pd 


dir_in = "./Model_Data/" 
rlids = [25, 29, 32, 34, 44] 
summer_months = ["2018-06", "2018-07", "2018-08"] 
autumn_months = ["2018-09", "2018-10", "2018-11"]
file_out_pattern = "RL{}_hvac_season4.csv" 

for rlid in rlids: 
    print("RLID: {}".format(rlid))
    #for filename in os.listdir(dir_in): 
    for month in autumn_months: 
        filepath = "{}RL{}_hvac_{}.csv".format(dir_in, rlid, month)

        
        df = pd.read_csv(filepath) 
        
        if "df_concat" not in globals(): 
            df_concat = df 
        else: 
            df_concat = pd.concat([df_concat, df]) 
            
    file_out = file_out_pattern.format(rlid)
    df_concat.to_csv(dir_in + file_out, index=False) 
    del df_concat 
        


