from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import swisseph as swe
import math
import datetime
import json


app = FastAPI()

# --- CORS for Lovable frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your Lovable domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------- Configuration --------------------------------
EPHE_PATH = None  # set to your ephemeris files folder if needed
PLANETS = [
    (swe.SUN, 'Sun'),
    (swe.MOON, 'Moon'),
    (swe.MERCURY, 'Mercury'),
    (swe.VENUS, 'Venus'),
    (swe.MARS, 'Mars'),
    (swe.JUPITER, 'Jupiter'),
    (swe.SATURN, 'Saturn'),
    (swe.MEAN_NODE, 'Rahu')  # we'll add Ketu as opposite
]

# Vimshottari sequence and proportions
VIMSHOTTARI_ORDER = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
VIM_YEARS = [7,20,6,10,7,18,16,19,17]
VIM_TOTAL = sum(VIM_YEARS)
#VIM_PROPORTIONS = [y / VIM_TOTAL for y in VIM_YEARS]
VIM_PROPORTIONS = [y/sum(VIM_YEARS) for y in VIM_YEARS]

# Nakshatra names and their lords (standard sequence starting from Ashwini)
NAK_SHAPES = [
    ('Ashwini','Ketu'),('Bharani','Venus'),('Krittika','Sun'),('Rohini','Moon'),('Mrigashira','Mars'),
    ('Ardra','Rahu'),('Punarvasu','Jupiter'),('Pushya','Saturn'),('Ashlesha','Mercury'),('Magha','Ketu'),
    ('Purva Phalguni','Venus'),('Uttara Phalguni','Sun'),('Hasta','Moon'),('Chitra','Mars'),('Swati','Rahu'),
    ('Vishakha','Jupiter'),('Anuradha','Saturn'),('Jyeshtha','Mercury'),('Mula','Ketu'),('Purva Ashadha','Venus'),
    ('Uttara Ashadha','Sun'),('Shravana','Moon'),('Dhanishta','Mars'),('Shatabhisha','Rahu'),('Purva Bhadrapada','Jupiter'),
    ('Uttara Bhadrapada','Saturn'),('Revati','Mercury')
]

# Sign rulers mapping (1..12 where 1=Aries)
SIGN_RULER = {
    1: 'Mars', 2: 'Venus', 3: 'Mercury', 4: 'Moon', 5: 'Sun', 6: 'Mercury',
    7: 'Venus', 8: 'Mars', 9: 'Jupiter', 10: 'Saturn', 11: 'Saturn', 12: 'Jupiter'
}
SIGN_NAMES = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

# -------------------- Helper functions --------------------------------

def parse_date_time(date_str, time_str):
    y,m,d = [int(x) for x in date_str.split('-')]
    hh,mm,ss = [int(x) for x in time_str.split(':')]
    return y,m,d,hh,mm,ss


def to_julian_day(year, month, day, hour=0, minute=0, second=0):
    ut_hours = hour + minute/60.0 + second/3600.0
    return swe.julday(year, month, day, ut_hours)


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

    nak_size = 360.0 / 27.0  # 13°20′ = 13.333333...
    nak_index = int(sid_deg // nak_size) + 1
    if nak_index > 27:
        nak_index = 27

    nak_name, nak_lord = NAK_SHAPES[nak_index - 1]

    nak_start = (nak_index - 1) * nak_size
    pos_in_nak = sid_deg - nak_start

    # Fix tiny floating negative due to rounding
    if pos_in_nak < 0:
        pos_in_nak += nak_size

    # Each nakshatra has 4 padas
    pada_size = nak_size / 4.0
    charan = int(pos_in_nak // pada_size) + 1
    if charan > 4:
        charan = 4

    return nak_index, nak_name, nak_lord, charan, pos_in_nak, nak_size


def find_sub_lord_recursive(pos_in_nak_deg, nak_size, nak_lord, levels=3):
    VIM_ORDER = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
    VIM_YEARS = [7,20,6,10,7,18,16,19,17]
    total = sum(VIM_YEARS)
    VIM_PROP = [y / total for y in VIM_YEARS]

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


@app.get("/")
def home():
    return {"message": "KP API running!"}

@app.get("/api/kp_chart")
def compute_kp_json(date_str:str, time_str:str, lat:float, lon:float, tz_offset_hours:float, ayan_mode='Lahiri'):
    """Compute KP JSON dict for given local date/time (with seconds) and location.
    ayan_mode: 'KP' or 'LAHIRI' (we set SWEPY sidereal mode accordingly)
    """
    global JD
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
    print(JD)
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
        print(cusp_sid)
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