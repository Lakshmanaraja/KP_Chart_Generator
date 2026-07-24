import swisseph as swe
from utils.constants import SIGN_NAMES, NAK_SHAPES, NAKSHATRA_SIZE, VIM_ORDER, VIM_PROP, VIM_YEARS

def to_julian_day(year, month, day, hour=0, minute=0, second=0):
    ut_hours = hour + minute/60.0 + second/3600.0
    return swe.julday(year, month, day, ut_hours)

def parse_date_time(date_str, time_str):
    y,m,d = [int(x) for x in date_str.split('-')]
    hh,mm,ss = [int(x) for x in time_str.split(':')]
    return y,m,d,hh,mm,ss

def normalize_angle(a):
    a = a % 360.0
    if a < 0:
        a += 360.0
    return a


def sign_from_deg(deg):
    deg = normalize_angle(deg)
    sign_idx = int(deg // 30) + 1
    sign_name = SIGN_NAMES[sign_idx - 1]
    return sign_idx, sign_name

def get_nak_charan_and_pos(sid_deg):
    # Normalize the degree
    sid_deg = sid_deg % 360.0
    nak_index = int(sid_deg // NAKSHATRA_SIZE) + 1
    if nak_index > 27:
        nak_index = 27

    nak_name, nak_lord = NAK_SHAPES[nak_index - 1]

    nak_start = (nak_index - 1) * NAKSHATRA_SIZE
    pos_in_nak = sid_deg - nak_start

    # Fix tiny floating negative due to rounding
    if pos_in_nak < 0:
        pos_in_nak += NAKSHATRA_SIZE

    # Each nakshatra has 4 padas
    pada_size = NAKSHATRA_SIZE / 4.0
    charan = int(pos_in_nak // pada_size) + 1
    if charan > 4:
        charan = 4

    return nak_index, nak_name, nak_lord, charan, pos_in_nak, NAKSHATRA_SIZE


def find_sub_lord_recursive(pos_in_nak_deg, nak_size, nak_lord, levels=3):

    total = sum(VIM_YEARS)
   

    # Rotate sequence so Nakshatra starts with its lord
    idx = VIM_ORDER.index(nak_lord)
    order = VIM_ORDER[idx:] + VIM_ORDER[:idx]
    props = VIM_PROP[idx:] + VIM_PROP[:idx]

    lords = []
    cur_pos = pos_in_nak_deg / nak_size  # normalize 0–1

    for _ in range(levels):
        cumulative = 0.0
        for lord, prop in zip(order, props):
            next_cum = cumulative + prop
            if cur_pos <= next_cum or abs(cur_pos - 1.0) < 1e-9:
                lords.append(lord)
                cur_pos = (cur_pos - cumulative) / prop
                # rotate again for next level starting from current sublord
                idx2 = VIM_ORDER.index(lord)
                order = VIM_ORDER[idx2:] + VIM_ORDER[:idx2]
                props = VIM_PROP[idx2:] + VIM_PROP[:idx2]
                break
            cumulative = next_cum

    return lords
    
def is_retrograde(jd, pconst, delta_days=2.0):
    lon1 = swe.calc_ut(jd, pconst)[0][0] if isinstance(swe.calc_ut(jd, pconst)[0], (list,tuple)) else swe.calc_ut(jd, pconst)[0]
    lon2 = swe.calc_ut(jd + delta_days, pconst)[0][0] if isinstance(swe.calc_ut(jd + delta_days, pconst)[0], (list,tuple)) else swe.calc_ut(jd + delta_days, pconst)[0]
    # normalize difference
    d = normalize_angle(lon2 - lon1)
    # if motion backwards more than 180 (i.e. negative real change), treat as retro
    # Better: if d > 180 then actual change is d-360 which is negative
    if d > 180:
        d = d - 360
    return d < 0

def get_moon_longitude(jd, lat, lon):
    swe.set_sid_mode(swe.SIDM_LAHIRI)  
    swe.set_topo(lon, lat, 0)

    pos, fl = swe.calc(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return pos[0]

# def dasha_balance(moon_long):
#     pos = moon_long % NAKSHATRA_SIZE
#     pct_done = pos / NAKSHATRA_SIZE
#     return 1 - pct_done

# --- FIX START ---
def get_nakshatra_index(moon_long):
    # Determine absolute Nakshatra placement from 0 to 26
    return int(moon_long // NAKSHATRA_SIZE)

