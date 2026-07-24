import swisseph as swe

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

VIMSHOTTARI_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17
}

#DASHA_ORDER = list(VIMSHOTTARI_YEARS.keys())
# Vimshottari sequence and proportions
VIM_ORDER = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
VIM_YEARS = [7,20,6,10,7,18,16,19,17]
VIM_TOTAL = sum(VIM_YEARS)
VIM_PROP = [y/VIM_TOTAL for y in VIM_YEARS]

#VIM_PROPORTIONS = [y / VIM_TOTAL for y in VIM_YEARS]


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

NAKSHATRA_SIZE = 13.33333333333333  # 13°20'
TOTAL_YEARS = 120
PLANET_SHORT_NAME_LIST = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']