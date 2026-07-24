import swisseph as swe
import datetime
import hashlib
import json

from models.schemas import BirthInput
from utils.constants import VIM_ORDER,VIMSHOTTARI_YEARS,TOTAL_YEARS,NAKSHATRA_SIZE
from database.redis_client import redis_client
from utils.date_utils import to_julian_day, get_moon_longitude,get_nakshatra_index


class ParentEndpointsNotCalledError(Exception):

    pass

# Utility: serialize datetime fields
def serialize(dashas):
    for d in dashas:
        if isinstance(d["start"], datetime.datetime):
            d["start"] = d["start"].isoformat()
        if isinstance(d["end"], datetime.datetime):
            d["end"] = d["end"].isoformat()
    return dashas

# Utility — convert string back to datetime
def deserialize(dashas):
    for d in dashas:
        d["start"] = datetime.datetime.fromisoformat(d["start"])
        d["end"]   = datetime.datetime.fromisoformat(d["end"])
    return dashas


# Helper: Generate birth hash for uniqueness
def birth_hash(data: BirthInput):
    txt = f"{data.year}{data.month}{data.day}{data.hour}{data.minutes}{data.seconds}{data.timezone}{data.latitude}{data.longitude}"
    return hashlib.md5(txt.encode()).hexdigest()[:6]


def dasha_balance(moon_long):
    nak_index = get_nakshatra_index(moon_long)
    
    # Track moon progress relative to the individual Nakshatra boundary line
    nak_start_long = nak_index * NAKSHATRA_SIZE
    degrees_spent = moon_long - nak_start_long
    
    pct_done = degrees_spent / NAKSHATRA_SIZE
    return 1 - pct_done

# def get_starting_dasha(moon_long):
#     nak = int(moon_long // NAKSHATRA_SIZE)
#     return DASHA_ORDER[nak % 9]

def get_starting_dasha(moon_long):
    nak = get_nakshatra_index(moon_long)
    return VIM_ORDER[nak % 9]



# --- FIX END ---

def circular_order_from(lord):
    idx = VIM_ORDER.index(lord)
    return VIM_ORDER[idx:] + VIM_ORDER[:idx]

# -------------------------------------------------------------------
#                      TIME RANGE UTILITY
# -------------------------------------------------------------------
def add_years(start, years):
    return start + datetime.timedelta(days=years * 365.25)

# -------------------------------------------------------------------
#                      MAJOR (MAHA) DASHA
# -------------------------------------------------------------------
def compute_major_dasha(start_datetime, moon_long):
    starting = get_starting_dasha(moon_long)
    balance = dasha_balance(moon_long)
     # 1. Calculate the hypothetical, full 120-year cycle start as if the person 
    # was born at the exact 0° mark of the Nakshatra (the true beginning)
    total_years_for_lord = VIMSHOTTARI_YEARS[starting]
    years_already_passed = total_years_for_lord * (1 - balance)
    #print("Starting Dasha:", starting)
    # Move the start date backwards in time to find the true, full Mahadasha beginning
    hypothetical_md_start = start_datetime - datetime.timedelta(days=years_already_passed * 365.25)
    hypothetical_md_end = hypothetical_md_start + datetime.timedelta(days=total_years_for_lord * 365.25)

    # 2. Run a temporary full Bhukti generation for this entire first Mahadasha block
    full_bhuktis = calculate_bhuktis(starting, hypothetical_md_start, hypothetical_md_end)

    # 3. Filter out Bhuktis that completely ended BEFORE the birth time,
    # and truncate the one active right at birth.
    valid_bhuktis = []
    for b in full_bhuktis:
        # If the Bhukti ended before birth, skip it entirely
        if b["end"] <= start_datetime:
            continue
        
        # If the Bhukti started before birth but ends after, it is active at birth!
        # Truncate its start date to the birth time.
        if b["start"] < start_datetime < b["end"]:
            b["start"] = start_datetime
            valid_bhuktis.append(b)
        else:
            # This Bhukti starts entirely after birth
            valid_bhuktis.append(b)

    # 4. Reconstruct the results list
    results = []
    
    # The true end of the first Mahadasha is when its last valid Bhukti ends
    first_md_end = valid_bhuktis[-1]["end"]
    results.append({"planet": starting, "start": start_datetime, "end": first_md_end})

    # 5. Build the remaining full Mahadashas of the 120-year cycle normally
    # reorder dasha cycle
    i = VIM_ORDER.index(starting)
    cycle = VIM_ORDER[i:] + VIM_ORDER[:i]

    results = []
    cur_start = start_datetime

    # first (reduced)
    first_year = VIMSHOTTARI_YEARS[starting] * balance
    first_end = add_years(cur_start, first_year)
    results.append({"planet": starting, "start": cur_start, "end": first_end})

    # rest
    cur = first_end
    for lord in cycle[1:]:
        yr = VIMSHOTTARI_YEARS[lord]
        end = add_years(cur, yr)
        results.append({"planet": lord, "start": cur, "end": end})
        cur = end

    return results


# -------------------------------------------------------------------
#                         BHUKTI (ANTAR DASHAS)
# -------------------------------------------------------------------
def calculate_bhuktis(md_lord, md_start, md_end):
    order = circular_order_from(md_lord)
    
    md_length = md_end - md_start   # in days
    current = md_start
    
    results = []
    for b_lord in order:
        part = md_length * (VIMSHOTTARI_YEARS[b_lord] / TOTAL_YEARS)
        results.append({
            "planet": b_lord,
            "start": current,
            "end": current + part
        })
        current += part

    return results


# -------------------------------------------------------------------
#                     ANTARA (PRATYANTAR DASHAS)
# -------------------------------------------------------------------
def calculate_antaras(bh_lord, bh_start, bh_end):
    order = circular_order_from(bh_lord)

    bh_length = bh_end - bh_start
    current = bh_start

    results = []
    for a_lord in order:
        part = bh_length * (VIMSHOTTARI_YEARS[a_lord] / TOTAL_YEARS)
        results.append({
            "planet": a_lord,
            "start": current,
            "end": current + part
        })
        current += part

    return results


# -------------------------------------------------------------------
#                   PRATYANTAR (SUKSHMA DASHAS)
# -------------------------------------------------------------------
def calculate_pratyantaras(an_lord, an_start, an_end):
    order = circular_order_from(an_lord)

    an_length = an_end - an_start
    current = an_start

    results = []
    for p_lord in order:
        part = an_length * (VIMSHOTTARI_YEARS[p_lord] / TOTAL_YEARS)
        results.append({
            "planet": p_lord,
            "start": current,
            "end": current + part
        })
        current += part

    return results



def major_vdasha(data: BirthInput):
    h = birth_hash(data)
    redis_key = f"dasha:v1:md:{h}"
    # check cache
    # Check cache first
    cached = redis_client.get(redis_key)
    if cached:
        return {"major_dasha": json.loads(cached)}

    #hour_utc = data.hour - data.timezone
    #jd = to_julian_day(data.year, data.month, data.day, hour_utc)

    local_dt = datetime.datetime(data.year,data.month,data.day,data.hour,data.minutes,data.seconds)
    ut_dt = local_dt - datetime.timedelta(hours=data.timezone)
    jd = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)
    moon_long = get_moon_longitude(jd, data.latitude, data.longitude)

    birth_dt = datetime.datetime(data.year, data.month, data.day) + datetime.timedelta(hours=data.hour,minutes=data.minutes,seconds=data.seconds)

    major_list = compute_major_dasha(birth_dt, moon_long)

    serialized = serialize(major_list)
    
    if not isinstance(serialized, list):
        serialized = [serialized]

    # save to redis with TTL (1 day)
    redis_client.set(redis_key, json.dumps(serialized), ex=86400)
    return {"major_dasha": serialized, "cached": False}

# --------------------------
# 2️⃣ API – BHUKTI for selected Mahadasha
# --------------------------
def sub_vdasha(data: BirthInput, md: str):
    h = birth_hash(data)
    md = md.lower()
    redis_key = f"dasha:v1:ad:{md}:{h}"

    cached = redis_client.get(redis_key)
    if cached:
        return {"md": md, "bhukti": json.loads(cached), "cached": True}

    md_key = f"dasha:v1:md:{h}"
    major_list_raw = redis_client.get(md_key)
    if not major_list_raw:
        ParentEndpointsNotCalledError("Call /major_vdasha first")
        

    major_list = json.loads(major_list_raw)
    major_list = deserialize(major_list)

    md_selected = next((d for d in major_list if d["planet"].lower() == md.lower()), None)
    if md_selected is None:
        ParentEndpointsNotCalledError("Mahadasha not found")

    birth_dt = major_list[0]["start"]          # Fixed list index lookup
    starting_md_lord = major_list[0]["planet"] # Fixed list index lookup

    if md_selected["planet"] == starting_md_lord:
        # Reconstruct the true historical start point before birth
        local_dt = datetime.datetime(data.year, data.month, data.day, data.hour, data.minutes, data.seconds)
        ut_dt = local_dt - datetime.timedelta(hours=data.timezone)
        jd = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)
        moon_long = get_moon_longitude(jd, data.latitude, data.longitude)
        
        balance = dasha_balance(moon_long)
        total_years = VIMSHOTTARI_YEARS[starting_md_lord]
        years_passed = total_years * (1 - balance)
        
        hypothetical_start = birth_dt - datetime.timedelta(days=years_passed * 365.25)
        hypothetical_end = hypothetical_start + datetime.timedelta(days=total_years * 365.25)
        
        full_bhuktis = calculate_bhuktis(starting_md_lord, hypothetical_start, hypothetical_end)
        
        bhuktis = []
        for b in full_bhuktis:
            if b["end"] <= birth_dt:
                continue
            if b["start"] < birth_dt < b["end"]:
                b["start"] = birth_dt
                bhuktis.append(b)
            else:
                bhuktis.append(b)
    else:
        # Standard un-truncated calculation for later Dasa blocks
        bhuktis = calculate_bhuktis(md_selected["planet"], md_selected["start"], md_selected["end"])

    bhuktis = serialize(bhuktis)
    if not isinstance(bhuktis, list):
        bhuktis = [bhuktis]
    redis_client.set(redis_key, json.dumps(bhuktis), ex=86400)

    return {"md": md, "bhukti": bhuktis, "cached": False}


# --------------------------
# 3️⃣ API – ANTARA (Pratyantar) for selected Bhukti
# --------------------------
def sub_sub_vdasha(data: BirthInput, md: str, ad: str):
    h = birth_hash(data)
    md = md.lower()
    ad = ad.lower()

    redis_key = f"dasha:v1:pd:{md}:{ad}:{h}"

    cached = redis_client.get(redis_key)
    if cached:
        return {"antara": json.loads(cached), "cached": True}

    # Fetch parent structures
    md_key = f"dasha:v1:md:{h}"
    major_list_raw = redis_client.get(md_key)
    bhukti_key = f"dasha:v1:ad:{md}:{h}"
    bhuktis_raw = redis_client.get(bhukti_key)
    
    if not bhuktis_raw or not major_list_raw:
        ParentEndpointsNotCalledError("Call parent endpoints first")

    major_list = deserialize(json.loads(major_list_raw))
    bhuktis = deserialize(json.loads(bhuktis_raw))
    
    birth_dt = major_list[0]["start"]
    starting_md_lord = major_list[0]["planet"]
    
    b_selected = next((b for b in bhuktis if b["planet"].lower() == ad), None)
    if b_selected is None:
        ParentEndpointsNotCalledError("Bhukti not found")

    # FIX: If we are tracking the active sub-dasha at birth, reconstruct the full window
    if md.lower() == starting_md_lord.lower() and b_selected["start"] == birth_dt:
        local_dt = datetime.datetime(data.year, data.month, data.day, data.hour, data.minutes, data.seconds)
        ut_dt = local_dt - datetime.timedelta(hours=data.timezone)
        jd = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)
        moon_long = get_moon_longitude(jd, data.latitude, data.longitude)
        
        balance = dasha_balance(moon_long)
        total_years = VIMSHOTTARI_YEARS[starting_md_lord]
        years_passed = total_years * (1 - balance)
        
        hypothetical_md_start = birth_dt - datetime.timedelta(days=years_passed * 365.25)
        hypothetical_md_end = hypothetical_md_start + datetime.timedelta(days=total_years * 365.25)
        
        # Pull original un-truncated parent Bhukti boundaries
        full_bhuktis = calculate_bhuktis(starting_md_lord, hypothetical_md_start, hypothetical_md_end)
        true_bhukti = next(b for b in full_bhuktis if b["planet"].lower() == ad)
        
        # Calculate nested Antaras from un-truncated windows, then apply slice filter
        full_antaras = calculate_antaras(true_bhukti["planet"], true_bhukti["start"], true_bhukti["end"])
        
        antaras = []
        for a in full_antaras:
            if a["end"] <= birth_dt:
                continue
            if a["start"] < birth_dt < a["end"]:
                a["start"] = birth_dt
                antaras.append(a)
            else:
                antaras.append(a)
    else:
        antaras = calculate_antaras(b_selected["planet"], b_selected["start"], b_selected["end"])

    antaras = serialize(antaras)
    if not isinstance(antaras, list):
        antaras = [antaras]
    redis_client.set(redis_key, json.dumps(antaras), ex=86400)

    return {"md": md, "ad": ad, "antara": antaras, "cached": False}

# --------------------------
# 4️⃣ API – PRATYANTAR (Sukshma Dashas) for selected Antara
# --------------------------
def sub_sub_sub_vdasha(data: BirthInput, md: str, ad: str, pd: str):
    h = birth_hash(data)
    md = md.lower()
    ad = ad.lower()
    pd = pd.lower()

    redis_key = f"dasha:v1:sd:{md}:{ad}:{pd}:{h}"

    cached = redis_client.get(redis_key)
    if cached:
        return {"pratyantara": json.loads(cached), "cached": True}

    # Fetch parent structures to check boundaries
    md_key = f"dasha:v1:md:{h}"
    major_list_raw = redis_client.get(md_key)
    bhukti_key = f"dasha:v1:ad:{md}:{h}"
    bhuktis_raw = redis_client.get(bhukti_key)
    antara_key = f"dasha:v1:pd:{md}:{ad}:{h}"
    antaras_raw = redis_client.get(antara_key)
    
    if not antaras_raw or not bhuktis_raw or not major_list_raw:
        ParentEndpointsNotCalledError("Call parent endpoints first")

    major_list = deserialize(json.loads(major_list_raw))
    antaras = deserialize(json.loads(antaras_raw))
    
    birth_dt = major_list[0]["start"]
    starting_md_lord = major_list[0]["planet"]
    
    a_selected = next((a for a in antaras if a["planet"].lower() == pd), None)
    if a_selected is None:
        ParentEndpointsNotCalledError("Antara (Pratyantar) not found")

    # FIX: If we are tracking the active Sukshma line running exactly at birth
    if md.lower() == starting_md_lord.lower() and a_selected["start"] == birth_dt:
        local_dt = datetime.datetime(data.year, data.month, data.day, data.hour, data.minutes, data.seconds)
        ut_dt = local_dt - datetime.timedelta(hours=data.timezone)
        jd = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)
        moon_long = get_moon_longitude(jd, data.latitude, data.longitude)
        
        balance = dasha_balance(moon_long)
        total_years = VIMSHOTTARI_YEARS[starting_md_lord]
        years_passed = total_years * (1 - balance)
        
        hypothetical_md_start = birth_dt - datetime.timedelta(days=years_passed * 365.25)
        hypothetical_md_end = hypothetical_md_start + datetime.timedelta(days=total_years * 365.25)
        
        # 1. Pull historical un-truncated Bhukti
        full_bhuktis = calculate_bhuktis(starting_md_lord, hypothetical_md_start, hypothetical_md_end)
        true_bhukti = next(b for b in full_bhuktis if b["planet"].lower() == ad)
        
        # 2. Pull historical un-truncated Antara
        full_antaras = calculate_antaras(true_bhukti["planet"], true_bhukti["start"], true_bhukti["end"])
        true_antara = next(a for a in full_antaras if a["planet"].lower() == pd)
        
        # 3. Calculate Sukshma from the un-truncated Antara, then slice out the past
        full_pratyantaras = calculate_pratyantaras(true_antara["planet"], true_antara["start"], true_antara["end"])
        
        pratyantaras = []
        for p in full_pratyantaras:
            if p["end"] <= birth_dt:
                continue
            if p["start"] < birth_dt < p["end"]:
                p["start"] = birth_dt
                pratyantaras.append(p)
            else:
                pratyantaras.append(p)
    else:
        # Standard un-truncated calculation for later periods or subsequent Mahadashas
        pratyantaras = calculate_pratyantaras(a_selected["planet"], a_selected["start"], a_selected["end"])

    pratyantaras = serialize(pratyantaras)
    if not isinstance(pratyantaras, list):
        pratyantaras = [pratyantaras]
    redis_client.set(redis_key, json.dumps(pratyantaras), ex=86400)

    return {"md": md, "ad": ad, "pd": pd, "pratyantara": pratyantaras, "cached": False}



def clear_cache():
    for key in redis_client.scan_iter("dasha:v1:*"):
        redis_client.delete(key)
    return {"status": "cleared"}
