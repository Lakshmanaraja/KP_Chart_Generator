import swisseph as swe

import json
import os
import datetime

#Not Needed
from typing import Optional, List, Dict, Any
from collections import defaultdict
import hashlib
import ast
import math


from utils.constants import EPHE_PATH,SIGN_NAMES,SIGN_RULER,NAK_SHAPES,TOTAL_YEARS,VIM_ORDER,VIM_YEARS,VIM_PROP,PLANETS,NAKSHATRA_SIZE
from utils.date_utils import to_julian_day,parse_date_time,normalize_angle,sign_from_deg,get_nak_charan_and_pos,find_sub_lord_recursive,is_retrograde




def compute_kp_json(date_str:str, time_str:str, lat:float, lon:float, tz_offset_hours:float, ayan_mode='Lahiri'):
    """Compute KP JSON dict for given local date/time (with seconds) and location.
    ayan_mode: 'KP' or 'LAHIRI' (we set SWEPY sidereal mode accordingly)
    """
    #global JD
    y,m,d,hh,mm,ss = parse_date_time(date_str, time_str)
    # convert local to UT
    local_dt = datetime.datetime(y,m,d,hh,mm,ss)
    ut_dt = local_dt - datetime.timedelta(hours=tz_offset_hours)
    JD = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)

    # set ephemeris path if provided
    if EPHE_PATH:
        swe.set_ephe_path(EPHE_PATH)

    # set sidereal mode to KP if requested
    if ayan_mode.upper().startswith('KP'):
        try:
            swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0, 0)
        except Exception:
            # fallback: leave default and rely on get_ayanamsa_ut
            pass
    else:
        try:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        except Exception:
            pass

    ayanamsha = swe.get_ayanamsa_ut(JD)

    out = {'ayanamsha': ayanamsha, 'houses': [], 'planets': []}

    # Planets
    for pconst, pname in PLANETS:
        calc = swe.calc_ut(JD, pconst)
        # calc sometimes returns nested structure; handle both
        if isinstance(calc[0], (list,tuple)):
            tropical_lon = calc[0][0]
        else:
            tropical_lon = calc[0]
        tropical_lon = normalize_angle(tropical_lon)
        sid_lon = normalize_angle(tropical_lon - ayanamsha)

        sign_id, sign_name = sign_from_deg(sid_lon)
        sign_lord = SIGN_RULER[sign_id]
        nak_idx, nak_name, nak_lord, charan, pos_in_nak, nak_size = get_nak_charan_and_pos(sid_lon)
        sub_lords = find_sub_lord_recursive(pos_in_nak, nak_size,nak_lord, levels=3)
        # determine retrograde
        retro = is_retrograde(JD, pconst)

        # determine house placement: find which house cusp the planet's sidereal longitude falls into
        # compute cusps to use for house determination
        #cusps, ascmc = swe.houses_ex(JD, lat, lon) if hasattr(swe, 'houses_ex') else swe.houses(JD, lat, lon)
        # normalize cusps list to length 12 starting indexes 1..12

        cusps, ascmc = swe.houses(JD, lat, lon) 
        if len(cusps) == 13:
            cusp_list = [cusps[i] for i in range(1,13)]
        elif len(cusps) == 12:
            cusp_list = [cusps[i] for i in range(0,12)]
        else:
            raise ValueError('Unexpected cusps length: %s' % len(cusps))
        # build ranges for houses (from cusp_i to cusp_{i+1})
        house_no = None
        for i in range(12):
            start = normalize_angle(cusp_list[i] - ayanamsha)
            end = normalize_angle((cusp_list[(i+1)%12] - ayanamsha))
            pdeg = sid_lon
            if start <= end:
                if pdeg >= start and pdeg < end:
                    house_no = i+1
                    break
            else:
                # wraps around 360
                if pdeg >= start or pdeg < end:
                    house_no = i+1
                    break
        if house_no is None:
            house_no = 12

        # house_lord is ruler of the sign on that cusp
        #cusp_sign_id = int(((normalize_angle(cusp_list[0] - ayanamsha) // 30)) + 1) if len(cusp_list) else None

        out['planets'].append({
            'planet_name': pname,
            'planet_id': list(map(lambda x: x[1], PLANETS)).index(pname),
            'full_degree': round(sid_lon, 6),
            'norm_degree': round(sid_lon % 30, 6),
            'is_retro': bool(retro),
            'sign_id': sign_id,
            'sign_name': sign_name,
            'sign_lord': sign_lord,
            'house': house_no,
            'house_lord': SIGN_RULER[((int((normalize_angle(cusp_list[house_no-1]-ayanamsha)//30))+1))],
            'nakshatra_name': nak_name,
            'nakshatra_id': nak_idx,
            'nakshatra_lord': nak_lord,
            'nakshatra_charan': charan,
            'sub_lord': sub_lords[0],
            'sub_sub_lord': sub_lords[1] if len(sub_lords) > 1 else None,
            'sub_sub_sub_lord': sub_lords[2] if len(sub_lords) > 2 else None
        })

   # Find Rahu data
    rahu = next((p for p in out['planets'] if p['planet_name'] == 'Rahu'), None)
    if rahu:
        ketu_sid_lon = normalize_angle(rahu['full_degree'] + 180)

        # Determine sign, nakshatra etc. same as above
        sign_id, sign_name = sign_from_deg(ketu_sid_lon)
        sign_lord = SIGN_RULER[sign_id]
        nak_idx, nak_name, nak_lord, charan, pos_in_nak, nak_size = get_nak_charan_and_pos(ketu_sid_lon)
        sub_lords = find_sub_lord_recursive(pos_in_nak, nak_size, nak_lord, levels=3)

        # Determine house for Ketu using same cusp logic
        house_no = None
        for i in range(12):
            start = normalize_angle(cusp_list[i] - ayanamsha)
            end = normalize_angle((cusp_list[(i + 1) % 12] - ayanamsha))
            pdeg = ketu_sid_lon
            if start <= end:
                if pdeg >= start and pdeg < end:
                    house_no = i + 1
                    break
            else:
                if pdeg >= start or pdeg < end:
                    house_no = i + 1
                    break
        if house_no is None:
            house_no = 12

        out['planets'].append({
            'planet_name': 'Ketu',
            'planet_id': 100,  # custom ID
            'full_degree': round(ketu_sid_lon, 6),
            'norm_degree': round(ketu_sid_lon % 30, 6),
            'is_retro': rahu['is_retro'],
            'sign_id': sign_id,
            'sign_name': sign_name,
            'sign_lord': sign_lord,
            'house': house_no,
            'house_lord': SIGN_RULER[((int((normalize_angle(cusp_list[house_no - 1] - ayanamsha) // 30)) + 1))],
            'nakshatra_name': nak_name,
            'nakshatra_id': nak_idx,
            'nakshatra_lord': nak_lord,
            'nakshatra_charan': charan,
            'sub_lord': sub_lords[0],
            'sub_sub_lord': sub_lords[1] if len(sub_lords) > 1 else None,
            'sub_sub_sub_lord': sub_lords[2] if len(sub_lords) > 2 else None
        })
     # Houses
    #cusps, ascmc = swe.houses_ex(JD, lat, lon) if hasattr(swe, 'houses_ex') else swe.houses(JD, lat, lon)
  
    JD = to_julian_day(ut_dt.year, ut_dt.month, ut_dt.day, ut_dt.hour, ut_dt.minute, ut_dt.second)
    #print(JD)
    cusps, ascmc = swe.houses(JD, lat, lon) 
    if len(cusps) == 13:
        cusp_list = [cusps[i] for i in range(1,13)]
    elif len(cusps) == 12:
        cusp_list = [cusps[i] for i in range(0,12)]
    else:
        raise ValueError('Unexpected cusps length: %s' % len(cusps))

    for i in range(12):
        cusp_trop = normalize_angle(cusp_list[i])
        cusp_sid = normalize_angle(cusp_trop - ayanamsha)
        #print(cusp_sid)
        sign_id, sign_name = sign_from_deg(cusp_sid)
        sign_lord = SIGN_RULER[sign_id]
        nak_idx, nak_name, nak_lord, charan, pos_in_nak, nak_size = get_nak_charan_and_pos(cusp_sid)
        
        sub_lords = find_sub_lord_recursive(pos_in_nak, nak_size,nak_lord, levels=3)

        out['houses'].append({
            'house_id': i+1,
            'full_degree': round(cusp_sid, 6),
            'norm_degree': round(cusp_sid % 30, 6),
            'sign_id': sign_id,
            'sign_name': sign_name,
            'sign_lord': sign_lord,
            'nakshatra_id': nak_idx,
            'nakshatra_name': nak_name,
            'nakshatra_lord': nak_lord,
            'nakshatra_charan': charan,
            'sub_lord': sub_lords[0],
            'sub_sub_lord': sub_lords[1] if len(sub_lords) > 1 else None,
            'sub_sub_sub_lord': sub_lords[2] if len(sub_lords) > 2 else None
        })

    return out