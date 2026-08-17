import pandas as pd
import numpy as np

# Define the expected structure for validation

from collections import defaultdict, Counter, OrderedDict
from typing import List, Dict, Any
import ast
import datetime

from services.chart_service import compute_kp_json
from utils.constants import PLANET_SHORT_NAME_LIST,VIM_ORDER,EPHE_PATH


def unique_list(pl_list):

    seen = set()
    unique_items = []

    for item in pl_list:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return(unique_items)

def calc_primary_pl_and_loc_pl(houses,planets,isPrimaryPL=1,isLoc=1):
    # group planets by house
    planets_by_house = {}
    for p in planets:
        planets_by_house.setdefault(p["house"], []).append(p)

    pr_pl_list = {}

    loc_list = {}

    for h in houses:
        
        pl_list = [h['nakshatra_lord'],h['sub_lord'],h['sub_sub_lord']]
        
        if len(set(pl_list)) < 3:
            pl_list.extend([h['sub_sub_sub_lord']]) #Filtered SNL

        pr_pl_list[h['house_id']] = unique_list(pl_list)

                
        plist = planets_by_house.get(h["house_id"], [])
        plist = sorted(plist, key=lambda x: x["full_degree"])

        for pl in plist:
            loc_list.setdefault(h['house_id'],[]).append(pl['planet_name'])
    
    combined_pl = {}

    if (isLoc==1):
        for k in set(pr_pl_list) | set(loc_list):
            combined_pl[k] = pr_pl_list.get(k, []) + loc_list.get(k, [])
    else :
            combined_pl = pr_pl_list

    return combined_pl


def calc_connected_planets(houses,planets):
    connected_pl = {}
    combined_pl = calc_primary_pl_and_loc_pl(houses,planets)

    for h in houses :
        #print(combined_pl[h['house_id']])
        connected_pl.setdefault(h['house_id'],[]).extend(combined_pl[h['house_id']])
        for pr_pl in combined_pl[h['house_id']]:
            for p in planets :
                #print(p)
                if pr_pl in [p['nakshatra_lord'],p['sub_lord']]:
                    
                    connected_pl[h['house_id']].append(p['planet_name'])
                    #break
                elif (pr_pl in [p['sub_sub_lord']]) & (p['nakshatra_lord']==p['sub_lord']) : #Filtered SSL

                     connected_pl[h['house_id']].append(p['planet_name'])   


    for h in houses :
        connected_pl[h['house_id']] = unique_list(connected_pl[h['house_id']])
        
    return(connected_pl)
    # Step 1: get all unique planet names
    
    
    #for pl in VIMSHOTTARI_ORDER:
        # Step 2: build presence matrix

def calc_bhava_planet_presence_fn (birth_date,birth_time,lat,lon,tz,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayan_mode='Lahiri'):

    if EPHE_PATH:
        swe.set_ephe_path(EPHE_PATH)
    #time = start_time
    kpjson = compute_kp_json(birth_date, birth_time, lat, lon, tz, ayan_mode='Lahiri')
    houses = sorted(kpjson["houses"], key=lambda x: x["house_id"])
    planets = sorted(kpjson["planets"], key=lambda x: x["house"])

    if(isConnectedPL == 1):
        bhava_planet_dict = calc_connected_planets(houses,planets)
    else :
        bhava_planet_dict = calc_primary_pl_and_loc_pl(houses,planets,isPrimaryPL,isLoc)
        
    presence = {}

    for house, planets in bhava_planet_dict.items():
        presence[house] = {pl: (1 if pl in planets else 0) for pl in VIM_ORDER}

        # Step 3: (optional) print as table
    return presence,kpjson

def compare_with_answer(df,answer_df):
    # Step 1: ensure same dtype (so comparisons behave cleanly)
    df = df.astype(int)
    answer_df = answer_df.astype(int)

    mask = (df != 2) & (answer_df != 2) 
    #print(mask)
    comparison = (df == answer_df) & mask

    matches = comparison.sum().sum()
    valid_points = mask.sum().sum()
    #mismatches = valid_points - matches


    # Step 3: find mismatches only within valid mask
    mismatch_mask = (df != answer_df) & mask
    # Step 4: get mismatch positions
    
    mismatch_locations = [(r + 1, c + 1) for r, c in zip(*np.where(mismatch_mask))]
    mismatch_values = []
    for location in mismatch_locations:
        r = location[0] - 1
        c = location[1] - 1
        mismatch_values.append((answer_df.iat[r,c],df.iat[r,c]))

    #print(mismatch_locations)
    return(matches / valid_points * 100 , mismatch_locations, mismatch_values)


def calc_bhava_planet_presence (birth_date:str,birth_time:str,lat:float,lon:float,tz:float,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayan_mode='Lahiri'):

    presence,kpjson = calc_bhava_planet_presence_fn(birth_date,birth_time,lat,lon,tz,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayan_mode='Lahiri')
    return presence,kpjson

def btr_correction(dateOfBirth:str,originalBirthTime:str,lat:float,lon:float,tz:float,time_delta:int,time_range:int,answer_chart:str,planet_order:str,must_not_mismatch:str,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayanamsa='Lahiri'):
    birth_date = dateOfBirth
    birth_time = originalBirthTime
    start_time = datetime.datetime.strptime(originalBirthTime, "%H:%M:%S") - datetime.timedelta(minutes=int(time_range))
    end_time = datetime.datetime.strptime(originalBirthTime, "%H:%M:%S") + datetime.timedelta(minutes=int(time_range))
    step = datetime.timedelta(seconds=int(time_delta))

    answer_list = ast.literal_eval(answer_chart)
    answer_df = pd.DataFrame(answer_list)
    answer_df.index += 1


    # (Optional) Add column names using planetOrder
    planet_list = ast.literal_eval(planet_order)
    answer_df.columns = planet_list

    must_not_mismatch_list = ast.literal_eval(must_not_mismatch)

    best_birth_time_list = {}
    i =0 

    #Loop
    current = start_time
    while current <= end_time:

        i = i+1
        birth_time = current.strftime("%H:%M:%S")

        presence,_ = calc_bhava_planet_presence_fn(birth_date,birth_time,lat,lon,tz,isPrimaryPL,isLoc,isConnectedPL,ayan_mode='Lahiri')
        df = pd.DataFrame.from_dict(presence, orient='index')
        percentage ,mismatch_locations, mismatch_values = compare_with_answer(df,answer_df)
        best_birth_time_list.setdefault(i,[]).append((birth_time,mismatch_locations,percentage,mismatch_values))

        if (step == datetime.timedelta(seconds=0)):
            break
        current += step

    

    #ignore_locations_text = [(3,'Mo'),(2,'Mo')] 
    ignore_locations = [
        (row, PLANET_SHORT_NAME_LIST.index(planet) + 1)
        for row, planet in must_not_mismatch_list
    ]

    # Flatten and exclude unwanted mismatches
    all_items = [
        (key, time, mismatches, float(score),mismatch_values)
        for key, lst  in best_birth_time_list.items()
        for time, mismatches, score , mismatch_values in lst
        if not any((int(r), int(c)) in ignore_locations for r, c in mismatches)
    ]

    #print(all_items)
    all_items_sorted_filtered = sorted(
        [item for item in all_items if item[3] >= 10.0],
        key=lambda x: x[3],
        reverse=True
        )

    print(f"Start Time : {start_time.time()}")
    print(f"End Time : {end_time.time()}")
    print(f"Total Number of Charts : {len(best_birth_time_list)}" )
    print(f"len of filtered:{len(all_items_sorted_filtered)}")

    results = []
    seen_mismatches = set()  # to track unique mismatch_str

    count = 0    
    for key, time, mismatches, score, mismatch_values in all_items_sorted_filtered:
        mismatch_str = ", ".join(
            f"({int(r)}, {PLANET_SHORT_NAME_LIST[int(c) - 1]}, {val1},{val2})"
            for (r, c), (val1, val2) in zip(mismatches, mismatch_values)
        )
        
        # skip duplicates
        if mismatch_str in seen_mismatches:
            continue
        
        seen_mismatches.add(mismatch_str)

        if (count > 3):
            break
        results.append({
            "chartNo": key,
            "time": time,
            "score": round(score, 2),
            "mismatches": mismatch_str
        })

        count = count + 1

    response = {
    "Start Time":start_time.time(),
    "End Time": end_time.time(),
    "total": len(best_birth_time_list),
    "results": results
    }
    return(response)

def bhava_planet_presence_for_questions(dateOfBirth:str,originalBirthTime:str,lat:float,lon:float,tz:float,time_delta:int,time_range:int,bhava_start:int,bhava_end:int,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayanamsa='Lahiri'):
    if EPHE_PATH:
        swe.set_ephe_path(EPHE_PATH)
  
    birth_date = dateOfBirth
    start_time = datetime.datetime.strptime(originalBirthTime, "%H:%M:%S") - datetime.timedelta(minutes=int(time_range))
    end_time = datetime.datetime.strptime(originalBirthTime, "%H:%M:%S") + datetime.timedelta(minutes=int(time_range))
    step = datetime.timedelta(seconds=int(time_delta))
    print(step)
    presence = {}
    current = start_time

    i = 0

    while current <= end_time:
        
        birth_time = current.strftime("%H:%M:%S")
        presence_new,_ = calc_bhava_planet_presence_fn(birth_date,birth_time,lat,lon,tz,isPrimaryPL,isLoc,isConnectedPL,ayan_mode='Lahiri')
        print(presence_new)
        if (i == 0) :
            presence = presence_new
        else :
            presence = { k: {planet: max(presence[k][planet], presence_new[k][planet]) for planet in presence[k]} for k in presence}
        
        i = i+1    
        if (step == datetime.timedelta(seconds=0)):
            break
        current += step

    for bhava in presence:
        if not (bhava_start <= bhava <= bhava_end):
            presence[bhava] = {planet: 2 for planet in presence[bhava]}
    #print(presence)
    return(presence) 
   


def aggregate(values):
    counter = Counter(values)
    most_common = counter.most_common()
    top_count = most_common[0][1]
    top_values = [v for v, c in most_common if c == top_count]

    if len(top_values) == 1:
        return top_values[0]
    tie = set(top_values)
    if tie == {0, 1}:
        return 2
    elif tie == {0, 2}:
        return 0
    elif tie == {1, 2}:
        return 1
    else:
        return 2  # all equal fallback

def calc_answer_chart(question_json: List[Dict]):
    # ---- STEP 1: Collect all selected values ----
    counts = defaultdict(list)

    for q in question_json:
        for combo in q["combinations"]:
            key = (combo["bhava"], combo["planet"])
            counts[key].append(q["selectedValue"])

    aggregated = defaultdict(dict)
    for (bhava, planet), values in counts.items():
        aggregated[bhava][planet] = aggregate(values)

    # ---- STEP 3: Build final ordered dictionary ----
    final_result = OrderedDict()

    for bhava in range(1, 13):
        # create bhava dictionary in fixed planet order
        bhava_dict = OrderedDict()
        for planet in VIM_ORDER:
            bhava_dict[planet] = aggregated.get(bhava, {}).get(planet, 2)
        final_result[bhava] = bhava_dict

    # ---- OUTPUT ----
    # from pprint import pprint
    # pprint(final_result)

    # Convert OrderedDict → regular dict for JSON serialization
    final_result_dict = {bhava: dict(planets) for bhava, planets in final_result.items()}
    return(final_result_dict)
    