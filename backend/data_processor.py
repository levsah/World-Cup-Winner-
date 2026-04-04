"""
data_processor.py
=================
Fetches raw data from api_client.py and transforms it into
normalised metric scores (0–100) used by the prediction model.

Key scores derived per team:
  - fifa_ranking_score      : Inverted / normalised rank (with embedded fallback)
  - recent_form_score       : Points earned in last 10 matches (team-perspective aware)
  - wc_history_score        : Past WC round progression average
  - squad_strength_score    : Squad completeness from API
  - player_performance_score: Per-team player quality from embedded ratings + API
  - goal_diff_score         : Goals scored − conceded (recent form window)
  - tournament_exp_score    : WC appearances count
"""

import logging
from typing import Any

import api_client as api

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedded FIFA rankings fallback (April 2026; based on official standings)
# Maps team_id → approximate rank  (only the 48 qualified teams)
# ---------------------------------------------------------------------------
FALLBACK_FIFA_RANKS: dict[int, int] = {
    # -----------------------------------------------------------------------
    # Sources: April 1, 2026 FIFA Rankings (confirmed top-20, Wikipedia) and
    # November 19, 2025 FIFA Rankings used for the 2026 WC draw seedings.
    # Playoff-winner ranks are estimates based on known squad strength.
    # -----------------------------------------------------------------------
    # Confirmed April 1, 2026 top-20 qualified teams
    9:    1,   # France
    15:   2,   # Spain
    7:    3,   # Argentina
    10:   4,   # England
    768:  5,   # Portugal
    6:    6,   # Brazil
    770:  7,   # Netherlands
    20:   8,   # Morocco
    762:  9,   # Belgium
    5:   10,   # Germany
    764: 11,   # Croatia
    26:  13,   # Colombia      (Italy #12 not qualified)
    32:  14,   # Senegal
    16:  15,   # Mexico
    3:   16,   # USA
    13:  17,   # Uruguay
    30:  18,   # Japan
    773: 19,   # Switzerland   (Denmark #20 not qualified)
    # Confirmed November 2025 draw rankings for remaining qualified teams
    801: 21,   # IR Iran        (was 20th, slight drop by April 2026)
    31:  22,   # South Korea
    21:  23,   # Ecuador
    769: 24,   # Austria
    800: 26,   # Australia
    43:  27,   # Canada         (co-host, FIFA rank 27)
    825: 28,   # Sweden         – qualified via play-off (UEFA Path B)
    829: 29,   # Norway
    45:  30,   # Panama
    806: 34,   # Egypt
    830: 35,   # Algeria
    772: 36,   # Scotland
    1523:38,   # Türkiye        – qualified via play-off (UEFA Path C)
    819: 39,   # Paraguay
    826: 40,   # Tunisia
    824: 42,   # Côte d'Ivoire
    765: 44,   # Czechia        – qualified via play-off (UEFA Path D)
    832: 50,   # Uzbekistan     – first World Cup
    # Estimated ranks for Pot-3 teams whose exact rank was not published
    803: 58,   # Qatar          (Pot 3 at draw, ~rank 58)
    802: 62,   # Saudi Arabia   (Pot 3 at draw, ~rank 62)
    820: 64,   # Bosnia and Herzegovina – qualified via play-off (UEFA Path A)
    831: 66,   # Congo DR       – qualified via play-off (IC Path 1)
    821: 68,   # South Africa   (Pot 3 at draw, ~rank 68)
    # Estimated ranks for Pot-4 teams (non-playoff)
    804: 72,   # Iraq           – qualified via play-off (IC Path 2)
    833: 74,   # Ghana          (Pot 4 at draw, ~rank 74)
    805: 76,   # Jordan         (Pot 4 at draw, ~rank 76) – first World Cup
    823: 84,   # Curaçao        (Pot 4 at draw, ~rank 84) – first World Cup
    828: 88,   # Cabo Verde     (Pot 4 at draw, ~rank 88) – first World Cup
    822: 92,   # Haiti          (Pot 4 at draw, ~rank 92)
    827: 103,  # New Zealand    (Pot 4 at draw, ~rank 103)
}

# ---------------------------------------------------------------------------
# Player quality scores (0–100) per team — calibrated to actual squad talent
# as of April 2026 (only the 48 finalists).
# Used as player_performance_score when API player stats are unavailable.
# ---------------------------------------------------------------------------
TEAM_PLAYER_QUALITY: dict[int, float] = {
    # CONMEBOL
    6:   92.0,  # Brazil        – Vinicius Jr, Endrick, Rodrygo, Marquinhos (Ancelotti era)
    7:   96.0,  # Argentina     – Messi, Enzo Fernandez, Álvarez, Almada; reigning WC champions
    26:  83.0,  # Colombia      – James Rodriguez, Luis Díaz, Sinisterra, Cuesta
    13:  76.0,  # Uruguay       – Darwin Núñez, Valverde, Bentancur, Araújo
    21:  70.0,  # Ecuador       – Moisés Caicedo, Plata, Sarmiento, Enner Valencia
    819: 67.0,  # Paraguay      – Miguel Almirón, Enciso, Adam; surprise 2026 qualifier
    # UEFA
    9:   95.0,  # France        – Mbappé, Tchouaméni, Thuram, Camavinga, Dembélé
    10:  90.0,  # England       – Bellingham, Saka, Foden, Palmer, Gordon, Alexander-Arnold
    15:  93.0,  # Spain         – Pedri, Lamine Yamal, Nico Williams, Dani Olmo, Rodri
    5:   86.0,  # Germany       – Florian Wirtz, Musiala, Havertz, Rüdiger, Kimmich
    768: 88.0,  # Portugal      – Bernardo Silva, Bruno Fernandes, Rafa Leão, Pedro Neto, Cancelo
    770: 84.0,  # Netherlands   – Van Dijk, De Jong, Gakpo, Dumfries, Bergwijn
    762: 79.0,  # Belgium       – De Bruyne, De Ketelaere, Doku, Tielemans
    764: 76.0,  # Croatia       – Modrić, Kovačić (veteran-led), Gvardiol, Pašalić
    773: 73.0,  # Switzerland   – Xhaka, Freuler, Embolo, Shaqiri era winding down
    825: 81.0,  # Sweden        – Viktor Gyokeres (world-class), Kulusevski, Forsberg, Elanga
    829: 83.0,  # Norway        – Erling Haaland, Ødegaard, Sörloth, Thorstvedt, Ajer
    820: 68.0,  # Bosnia & Herz – Tabakovic, Hajradinović, Paljić; surprised Italy in play-offs
    765: 67.0,  # Czechia       – Souček, Hlozek, Sulc, Krejci; beat Denmark on pens
    769: 76.0,  # Austria       – Sabitzer, Laimer, Baumgartner, Wimmer
    772: 65.0,  # Scotland      – Robertson, McTominay, Adams, Tierney; dramatic qualifier
    1523:74.0,  # Türkiye       – Arda Güler, Kenan Yıldız, Çalhanoğlu, Kokcu
    # CONCACAF
    3:   79.0,  # USA           – Pulisic, Reyna, Weah, Turner, McKennie, Tillman
    16:  72.0,  # Mexico        – Giménez, Calderón, Antuna, Gallardo
    43:  77.0,  # Canada        – Alphonso Davies, Jonathan David, Buchanan, Johnston
    45:  58.0,  # Panama        – Blackman, Godoy, Davis Córdoba
    823: 56.0,  # Curaçao       – Gyrano Kerk, Joel Piroe; first WC, Dutch-Caribbean talent
    822: 53.0,  # Haiti         – Nazon, Carlinhos; first WC since 1974
    # AFC
    30:  81.0,  # Japan         – Kubo, Mitoma, Endo, Itakura, Tomiyasu
    31:  76.0,  # South Korea   – Son Heung-min, Lee Kang-in, Kim Min-jae, Hwang Hee-chan
    800: 70.0,  # Australia     – Kuol, Devlin, Souttar, Ryan; sixth successive WC
    801: 63.0,  # IR Iran       – Azmoun, Taremi, Jahanbakhsh, Hosseini
    802: 60.0,  # Saudi Arabia  – Al-Dawsari, Al-Shahrani, Firas Al-Buraikan
    803: 55.0,  # Qatar         – Afif, Hassan, Boudiaf; host of 2022
    804: 57.0,  # Iraq          – Ali Al-Hamadi, Aymen Hussein; back after 40 years
    805: 55.0,  # Jordan        – Baha Faisal; maiden World Cup
    832: 62.0,  # Uzbekistan    – Shomurodov, Abdukhodirov; maiden World Cup
    # CAF
    20:  82.0,  # Morocco       – Hakimi, Mazraoui, En-Nesyri, Ziyech, Amallah
    32:  80.0,  # Senegal       – Ismaïla Sarr, Diallo, Faye, Gueye
    806: 66.0,  # Egypt         – Mohamed Salah (still world-class), Ibrahim Adel
    830: 74.0,  # Algeria       – Riyad Mahrez, Benrahma, Zerrouki, Ounahi
    824: 77.0,  # Côte d'Ivoire – Haller, Kessié, Koné, Simon; AFCON 2023 champions
    833: 68.0,  # Ghana         – Kudus, Semenyo, Kamaldeen Sulemana, Aidoo
    826: 65.0,  # Tunisia       – Msakni, Khazri era winding down; disciplined squad
    821: 62.0,  # South Africa  – Percy Tau, Makgopa, Ronwen Williams; ended 16-year WC absence
    831: 65.0,  # Congo DR      – Bakambu, Mbemba, Tuanzebe, Bongonda; play-off victors
    828: 60.0,  # Cabo Verde    – Tavares, Baldé; first World Cup, some Ligue 1 quality
    # OFC
    827: 54.0,  # New Zealand   – Kuol (diaspora), Ryan; third WC campaign
}

# ---------------------------------------------------------------------------
# Squad depth scores (0–100) — represents bench quality / 26-man squad depth,
# distinct from individual star quality in TEAM_PLAYER_QUALITY.
# Used as squad_strength_score when API squad data is unavailable.
# ---------------------------------------------------------------------------
FALLBACK_SQUAD_DEPTH: dict[int, float] = {
    9:    92.0,  # France        – exceptional depth at every position
    10:   90.0,  # England       – deep PL-based squad
    15:   88.0,  # Spain         – La Masia pipeline, quality throughout
    5:    88.0,  # Germany       – Bundesliga depth
    6:    87.0,  # Brazil        – talent-rich across all lines
    768:  84.0,  # Portugal      – strong first 21, thin 22-26
    770:  84.0,  # Netherlands   – Eredivisie + top-5 league mix
    829:  82.0,  # Norway        – Haaland + quality youngsters
    7:    82.0,  # Argentina     – elite starters, thinner backup unit
    773:  80.0,  # Switzerland   – organised, solid bench
    825:  80.0,  # Sweden        – Gyokeres + reasonable depth
    3:    79.0,  # USA           – growing depth (MLS + Europe)
    30:   79.0,  # Japan         – European-based bench quality improving
    762:  76.0,  # Belgium       – aging golden gen, limited replacements
    764:  74.0,  # Croatia       – Modrić era; depth thinner now
    31:   76.0,  # South Korea   – Son + solid European-based squad
    26:   77.0,  # Colombia      – quality across CONMEBOL level
    43:   76.0,  # Canada        – strong first gen as hosts
    16:   78.0,  # Mexico        – solid Liga MX + European contingent
    13:   74.0,  # Uruguay       – historically strong but ageing
    20:   74.0,  # Morocco       – strong first 18, thinner bench
    32:   72.0,  # Senegal       – first team quality, bench drops off
    769:  74.0,  # Austria       – Bundesliga quality, decent depth
    21:   72.0,  # Ecuador       – reliable CONMEBOL mid-tier
    1523: 76.0,  # Türkiye       – good Süper Lig + European players
    772:  70.0,  # Scotland      – decent across Scottish/English leagues
    830:  70.0,  # Algeria       – French-Algerian player pool
    824:  72.0,  # Côte d'Ivoire – AFCON talent, some bench drop-off
    800:  70.0,  # Australia     – A-League + some European players
    806:  65.0,  # Egypt         – Salah + limited depth
    765:  72.0,  # Czechia       – decent European base
    833:  66.0,  # Ghana         – European-based but thin bench
    826:  65.0,  # Tunisia       – disciplined, not deep
    801:  66.0,  # IR Iran       – limited European presence
    819:  64.0,  # Paraguay      – CONMEBOL regulars
    802:  64.0,  # Saudi Arabia  – improving but limited internationally
    45:   60.0,  # Panama        – solid CONCACAF, limited depth
    820:  66.0,  # Bosnia        – European-based, thin beyond first 15
    821:  62.0,  # South Africa  – improving PSL + some Europe
    831:  62.0,  # Congo DR      – quality spots, overall thin squad
    803:  62.0,  # Qatar         – mostly domestic league + Gulf
    804:  60.0,  # Iraq          – limited international experience
    832:  58.0,  # Uzbekistan    – developing; mainly domestic + Russian league
    828:  56.0,  # Cabo Verde    – Portuguese league connections
    805:  56.0,  # Jordan        – debut; limited depth
    827:  55.0,  # New Zealand   – A-League basis, thin quality
    822:  52.0,  # Haiti         – CONCACAF-based, limited depth
    823:  50.0,  # Curaçao       – small pool, Dutch-based diaspora
}

# ---------------------------------------------------------------------------
# WC History scores (0–100) — average performance across last 5 WCs (2006–2022).
# Higher = deeper tournament runs consistently.
# Used as wc_history_score when API WC fixture data is unavailable.
# ---------------------------------------------------------------------------
FALLBACK_WC_HISTORY: dict[int, float] = {
    7:    70.0,  # Argentina     – 2022 Winner, 2014 Final, QF others
    9:    68.0,  # France        – 2018 Winner, 2022 Final, consistent
    764:  58.0,  # Croatia       – 2018 Final, 2022 3rd place
    6:    52.0,  # Brazil        – 5 titles historically; recent QF exits
    5:    44.0,  # Germany       – 2014 Winner; 2018/2022 group stage
    770:  44.0,  # Netherlands   – 2010 Final, 2014 3rd, missed 2018
    13:   40.0,  # Uruguay       – 2010 SF, 2018 QF, consistent
    10:   38.0,  # England       – 2018 SF, 2022 QF, improving
    15:   38.0,  # Spain         – 2010 Winner, poor 2014/2018/2022
    768:  36.0,  # Portugal      – consistent QF/R16, no final
    762:  32.0,  # Belgium       – 2018 3rd, rest GS/R16
    20:   28.0,  # Morocco       – 2022 SF!, rest early exits
    773:  26.0,  # Switzerland   – 2022 QF, consistent R16 performer
    26:   24.0,  # Colombia      – 2014 QF, 2018 R16
    3:    22.0,  # USA           – consistent R16 performer (missed 2018)
    30:   22.0,  # Japan         – 2022 R16, 2018 R16, consistent
    31:   22.0,  # South Korea   – 2022 R16, 2010 R16, reliable WC team
    16:   22.0,  # Mexico        – perennial R16 team
    833:  20.0,  # Ghana         – 2010 QF!, consistent WC presence
    800:  20.0,  # Australia     – 2022 R16, 2006 R16
    1523: 14.0,  # Türkiye       – 2002 3rd (outside window); absent since
    826:  14.0,  # Tunisia       – multiple GS-only appearances
    825:  14.0,  # Sweden        – 2018 QF!, otherwise absent
    819:  14.0,  # Paraguay      – 2010 QF!, 2006 R16, then absent
    32:   14.0,  # Senegal       – 2022 R16, 2010 GS, sporadic
    802:  14.0,  # Saudi Arabia  – 2022 R16 heroics!, 2018 GS
    21:   12.0,  # Ecuador       – 2006 R16, 2022 GS, others absent
    801:  12.0,  # IR Iran       – 4 WC appearances, all group stage
    830:  12.0,  # Algeria       – 2014 R16, others GS/absent
    824:  10.0,  # Côte d'Ivoire – 2006/2010/2014 all GS
    43:   10.0,  # Canada        – 2022 GS; 1986 only other WC
    803:   8.0,  # Qatar         – 2022 GS as host
    769:   8.0,  # Austria       – 2006 R16, absent since
    806:   8.0,  # Egypt         – 2018 GS; long absence otherwise
    765:   8.0,  # Czechia       – Czech Republic 2006 GS only (in window)
    820:   8.0,  # Bosnia        – 2014 GS only
    821:   6.0,  # South Africa  – 2010 GS as host
    45:    6.0,  # Panama        – 2018 GS, first and only WC
    829:   6.0,  # Norway        – last WC 1998, multiple failed qualifications
    772:   6.0,  # Scotland      – last WC 1998
    827:   6.0,  # New Zealand   – 2010 GS only
    804:   5.0,  # Iraq          – last WC 1986
    831:   5.0,  # Congo DR      – last WC 1974 (as Zaire)
    832:   5.0,  # Uzbekistan    – first WC
    805:   5.0,  # Jordan        – first WC
    828:   5.0,  # Cabo Verde    – first WC
    822:   5.0,  # Haiti         – last WC 1974
    823:   5.0,  # Curaçao       – first WC
}

# ---------------------------------------------------------------------------
# Tournament experience scores (0–100) — (WC appearances in last 5 / 5) × 100.
# Captures how regularly a team qualifies, rewarding consistent qualification.
# Used as tournament_exp_score when API data is unavailable.
# ---------------------------------------------------------------------------
FALLBACK_TOURNAMENT_EXP: dict[int, float] = {
    6:   100.0,  # Brazil        – 5/5 (never missed a WC)
    5:   100.0,  # Germany       – 5/5
    7:   100.0,  # Argentina     – 5/5
    9:   100.0,  # France        – 5/5
    15:  100.0,  # Spain         – 5/5
    768: 100.0,  # Portugal      – 5/5
    10:  100.0,  # England       – 5/5
    16:  100.0,  # Mexico        – 5/5
    30:  100.0,  # Japan         – 5/5
    773: 100.0,  # Switzerland   – 5/5
    31:   80.0,  # South Korea   – 4/5 (consistent qualifier)
    801:  80.0,  # IR Iran       – 4/5 (2006/2014/2018/2022)
    762:  80.0,  # Belgium       – 4/5 (missed 2006)
    770:  80.0,  # Netherlands   – 4/5 (missed 2018)
    13:   80.0,  # Uruguay       – 4/5 (missed 2006)
    764:  80.0,  # Croatia       – 4/5 (missed 2010)
    3:    80.0,  # USA           – 4/5 (missed 2018)
    833:  80.0,  # Ghana         – 4/5 (2006/2010/2014/2022)
    800:  60.0,  # Australia     – 3/5 (2006/2014/2022)
    21:   60.0,  # Ecuador       – 3/5 (2006/2014/2022)
    826:  60.0,  # Tunisia       – 3/5 (2006/2018/2022)
    802:  60.0,  # Saudi Arabia  – 3/5 (2014/2018/2022)
    824:  60.0,  # Côte d'Ivoire – 3/5 (2006/2010/2014)
    26:   40.0,  # Colombia      – 2/5 (2014/2018)
    20:   40.0,  # Morocco       – 2/5 (2018/2022)
    32:   40.0,  # Senegal       – 2/5 (2010/2022)
    830:  40.0,  # Algeria       – 2/5 (2010/2014)
    825:  40.0,  # Sweden        – 2/5 (2006/2018)
    819:  40.0,  # Paraguay      – 2/5 (2006/2010)
    43:   20.0,  # Canada        – 1/5 (2022 only in window)
    803:  20.0,  # Qatar         – 1/5 (2022 as host)
    769:  20.0,  # Austria       – 1/5 (2006 only)
    806:  20.0,  # Egypt         – 1/5 (2018 only)
    45:   20.0,  # Panama        – 1/5 (2018 only)
    820:  20.0,  # Bosnia        – 1/5 (2014 only)
    821:  20.0,  # South Africa  – 1/5 (2010 as host)
    765:  20.0,  # Czechia       – 1/5 (Czech Republic 2006)
    827:  20.0,  # New Zealand   – 1/5 (2010 only)
    829:   0.0,  # Norway        – 0/5 (last WC 1998)
    772:   0.0,  # Scotland      – 0/5 (last WC 1998)
    1523:  0.0,  # Türkiye       – 0/5 (last WC 2002)
    804:   0.0,  # Iraq          – 0/5 (last WC 1986)
    831:   0.0,  # Congo DR      – 0/5 (last WC 1974)
    832:   0.0,  # Uzbekistan    – 0/5 (first WC)
    805:   0.0,  # Jordan        – 0/5 (first WC)
    828:   0.0,  # Cabo Verde    – 0/5 (first WC)
    822:   0.0,  # Haiti         – 0/5 (last WC 1974)
    823:   0.0,  # Curaçao       – 0/5 (first WC)
}

# ---------------------------------------------------------------------------
# 2026 World Cup: 48 qualified teams — FINAL DRAW (Washington DC, Nov 2025)
# Groups A–L (12 × 4) as drawn; IDs from API-Football v3.
# Playoff results (March 2026): Bosnia beat Italy, Czechia beat Denmark,
# Sweden beat Poland, Türkiye beat Kosovo, Iraq beat Bolivia, Congo DR beat Jamaica.
# ---------------------------------------------------------------------------
QUALIFIED_TEAMS: list[dict] = [
    # ── Group A ──────────────────────────────────────────────────────────
    {"id": 16,   "name": "Mexico",               "confederation": "CONCACAF", "flag": "🇲🇽", "group": "A"},
    {"id": 821,  "name": "South Africa",          "confederation": "CAF",      "flag": "🇿🇦", "group": "A"},
    {"id": 31,   "name": "South Korea",           "confederation": "AFC",      "flag": "🇰🇷", "group": "A"},
    {"id": 765,  "name": "Czechia",               "confederation": "UEFA",     "flag": "🇨🇿", "group": "A"},
    # ── Group B ──────────────────────────────────────────────────────────
    {"id": 43,   "name": "Canada",                "confederation": "CONCACAF", "flag": "🇨🇦", "group": "B"},
    {"id": 820,  "name": "Bosnia and Herzegovina","confederation": "UEFA",     "flag": "🇧🇦", "group": "B"},
    {"id": 803,  "name": "Qatar",                 "confederation": "AFC",      "flag": "🇶🇦", "group": "B"},
    {"id": 773,  "name": "Switzerland",           "confederation": "UEFA",     "flag": "🇨🇭", "group": "B"},
    # ── Group C ──────────────────────────────────────────────────────────
    {"id": 6,    "name": "Brazil",                "confederation": "CONMEBOL", "flag": "🇧🇷", "group": "C"},
    {"id": 20,   "name": "Morocco",               "confederation": "CAF",      "flag": "🇲🇦", "group": "C"},
    {"id": 822,  "name": "Haiti",                 "confederation": "CONCACAF", "flag": "🇭🇹", "group": "C"},
    {"id": 772,  "name": "Scotland",              "confederation": "UEFA",     "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "group": "C"},
    # ── Group D ──────────────────────────────────────────────────────────
    {"id": 3,    "name": "USA",                   "confederation": "CONCACAF", "flag": "🇺🇸", "group": "D"},
    {"id": 819,  "name": "Paraguay",              "confederation": "CONMEBOL", "flag": "🇵🇾", "group": "D"},
    {"id": 800,  "name": "Australia",             "confederation": "AFC",      "flag": "🇦🇺", "group": "D"},
    {"id": 1523, "name": "Türkiye",               "confederation": "UEFA",     "flag": "🇹🇷", "group": "D"},
    # ── Group E ──────────────────────────────────────────────────────────
    {"id": 5,    "name": "Germany",               "confederation": "UEFA",     "flag": "🇩🇪", "group": "E"},
    {"id": 823,  "name": "Curaçao",               "confederation": "CONCACAF", "flag": "🇨🇼", "group": "E"},
    {"id": 824,  "name": "Côte d'Ivoire",         "confederation": "CAF",      "flag": "🇨🇮", "group": "E"},
    {"id": 21,   "name": "Ecuador",               "confederation": "CONMEBOL", "flag": "🇪🇨", "group": "E"},
    # ── Group F ──────────────────────────────────────────────────────────
    {"id": 770,  "name": "Netherlands",           "confederation": "UEFA",     "flag": "🇳🇱", "group": "F"},
    {"id": 30,   "name": "Japan",                 "confederation": "AFC",      "flag": "🇯🇵", "group": "F"},
    {"id": 825,  "name": "Sweden",                "confederation": "UEFA",     "flag": "🇸🇪", "group": "F"},
    {"id": 826,  "name": "Tunisia",               "confederation": "CAF",      "flag": "🇹🇳", "group": "F"},
    # ── Group G ──────────────────────────────────────────────────────────
    {"id": 762,  "name": "Belgium",               "confederation": "UEFA",     "flag": "🇧🇪", "group": "G"},
    {"id": 806,  "name": "Egypt",                 "confederation": "CAF",      "flag": "🇪🇬", "group": "G"},
    {"id": 801,  "name": "IR Iran",               "confederation": "AFC",      "flag": "🇮🇷", "group": "G"},
    {"id": 827,  "name": "New Zealand",           "confederation": "OFC",      "flag": "🇳🇿", "group": "G"},
    # ── Group H ──────────────────────────────────────────────────────────
    {"id": 15,   "name": "Spain",                 "confederation": "UEFA",     "flag": "🇪🇸", "group": "H"},
    {"id": 828,  "name": "Cabo Verde",            "confederation": "CAF",      "flag": "🇨🇻", "group": "H"},
    {"id": 802,  "name": "Saudi Arabia",          "confederation": "AFC",      "flag": "🇸🇦", "group": "H"},
    {"id": 13,   "name": "Uruguay",               "confederation": "CONMEBOL", "flag": "🇺🇾", "group": "H"},
    # ── Group I ──────────────────────────────────────────────────────────
    {"id": 9,    "name": "France",                "confederation": "UEFA",     "flag": "🇫🇷", "group": "I"},
    {"id": 32,   "name": "Senegal",               "confederation": "CAF",      "flag": "🇸🇳", "group": "I"},
    {"id": 804,  "name": "Iraq",                  "confederation": "AFC",      "flag": "🇮🇶", "group": "I"},
    {"id": 829,  "name": "Norway",                "confederation": "UEFA",     "flag": "🇳🇴", "group": "I"},
    # ── Group J ──────────────────────────────────────────────────────────
    {"id": 7,    "name": "Argentina",             "confederation": "CONMEBOL", "flag": "🇦🇷", "group": "J"},
    {"id": 830,  "name": "Algeria",               "confederation": "CAF",      "flag": "🇩🇿", "group": "J"},
    {"id": 769,  "name": "Austria",               "confederation": "UEFA",     "flag": "🇦🇹", "group": "J"},
    {"id": 805,  "name": "Jordan",                "confederation": "AFC",      "flag": "🇯🇴", "group": "J"},
    # ── Group K ──────────────────────────────────────────────────────────
    {"id": 768,  "name": "Portugal",              "confederation": "UEFA",     "flag": "🇵🇹", "group": "K"},
    {"id": 831,  "name": "Congo DR",              "confederation": "CAF",      "flag": "🇨🇩", "group": "K"},
    {"id": 832,  "name": "Uzbekistan",            "confederation": "AFC",      "flag": "🇺🇿", "group": "K"},
    {"id": 26,   "name": "Colombia",              "confederation": "CONMEBOL", "flag": "🇨🇴", "group": "K"},
    # ── Group L ──────────────────────────────────────────────────────────
    {"id": 10,   "name": "England",               "confederation": "UEFA",     "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "group": "L"},
    {"id": 764,  "name": "Croatia",               "confederation": "UEFA",     "flag": "🇭🇷", "group": "L"},
    {"id": 833,  "name": "Ghana",                 "confederation": "CAF",      "flag": "🇬🇭", "group": "L"},
    {"id": 45,   "name": "Panama",                "confederation": "CONCACAF", "flag": "🇵🇦", "group": "L"},
]

# Historical WC round mapping (round name → points)
ROUND_POINTS = {
    "Winner":          7,
    "Final":           6,
    "Semi-finals":     5,
    "Quarter-finals":  4,
    "Round of 16":     3,
    "Group Stage":     1,
}

# Number of WC tournaments available in API
MAX_WC_SEASONS = [2022, 2018, 2014, 2010, 2006]

# ---------------------------------------------------------------------------
# Metric builders
# ---------------------------------------------------------------------------

def _compute_form_score(fixtures: list[dict], team_id: int) -> tuple[float, float]:
    """
    Returns (form_score 0–100, goal_diff_score 0–100) from recent fixtures.
    Correctly identifies whether ``team_id`` is the home or away side in
    each fixture so wins/losses are attributed to the right team.

    form_score  = (points / max_points) * 100
    goal_diff   = normalised from [-20, +20] → [0, 100]
    """
    if not fixtures:
        return 50.0, 50.0  # no data — use neutral fallback
    points = 0
    goal_diff = 0
    for fix in fixtures:
        teams      = fix.get("teams", {})
        goals      = fix.get("goals", {})
        home_id    = teams.get("home", {}).get("id")

        home_goals = goals.get("home") or 0
        away_goals = goals.get("away") or 0

        # Determine which side our team played on
        is_home    = (team_id == home_id)
        team_goals = home_goals if is_home else away_goals
        opp_goals  = away_goals if is_home else home_goals

        goal_diff += team_goals - opp_goals

        if team_goals > opp_goals:
            points += 3
        elif team_goals == opp_goals:
            points += 1
        # else: loss → 0 points

    max_points = len(fixtures) * 3 if fixtures else 1
    form_score = min((points / max_points) * 100, 100)
    # Normalise goal_diff from [-20, +20] → [0, 100]
    gd_score   = max(0.0, min(100.0, (goal_diff + 20) * 2.5))
    return form_score, gd_score


def _compute_wc_history_score(wc_fixtures: list[dict]) -> tuple[float, float]:
    """
    Returns (wc_history_score, tournament_exp_score).
    wc_history_score = avg round reached across tournaments, normalised.
    tournament_exp   = # distinct WC seasons appeared, normalised to 5 max.
    """
    if not wc_fixtures:
        return 10.0, 10.0

    round_pts = []
    seasons_seen: set[int] = set()
    for fix in wc_fixtures:
        season = fix.get("league", {}).get("season")
        if season:
            seasons_seen.add(season)
        round_name = fix.get("league", {}).get("round", "")
        for key, val in ROUND_POINTS.items():
            if key.lower() in round_name.lower():
                round_pts.append(val)
                break

    avg_round    = sum(round_pts) / len(round_pts) if round_pts else 1
    hist_score   = min((avg_round / 7) * 100, 100)
    exp_score    = min((len(seasons_seen) / 5) * 100, 100)
    return hist_score, exp_score


def _compute_squad_strength(squad_data: list[dict]) -> float:
    """
    Squad completeness score (0–100): rewards a full 23-man roster.
    This is intentionally a minor metric; actual player quality is captured
    by ``player_performance_score`` via ``TEAM_PLAYER_QUALITY``.
    """
    if not squad_data:
        return 50.0

    players = []
    for entry in squad_data:
        players.extend(entry.get("players", []))

    if not players:
        return 50.0

    # Completeness: 23-man squad = 100, fewer = proportionally less
    return min(len(players) / 23, 1.0) * 100


def _compute_player_performance_score(team_id: int, squad_data: list[dict]) -> float:
    """
    Player quality score (0–100).

    Primary:  ``TEAM_PLAYER_QUALITY[team_id]`` — hand-calibrated talent tier
              reflecting current squad stars, depth, and club-level output.
    Bonus:    If the API squad returns ≥21 players with varied positions,
              add a small completeness bonus (up to +3 pts) to reward depth.
    Fallback: 55.0 for any unrecognised team_id.
    """
    base = TEAM_PLAYER_QUALITY.get(team_id, 55.0)

    # Small API-based depth bonus
    players: list[dict] = []
    for entry in squad_data:
        players.extend(entry.get("players", []))
    positions = {p.get("position", "") for p in players}
    depth_bonus = 0.0
    if len(players) >= 21 and len(positions) >= 3:
        depth_bonus = 3.0

    return min(100.0, base + depth_bonus)


# ---------------------------------------------------------------------------
# Main orchestrator — build full metric profile for a team
# ---------------------------------------------------------------------------

def build_team_profile(team: dict) -> dict:
    """
    Fetches all relevant API data for a team and returns a normalised
    metric profile dict used by the predictor.
    """
    team_id   = team["id"]
    team_name = team["name"]
    logger.info("Building profile for %s (id=%s)", team_name, team_id)

    profile: dict[str, Any] = {
        "id":            team_id,
        "name":          team_name,
        "flag":          team.get("flag", ""),
        "confederation": team.get("confederation", ""),
        "group":         team.get("group", ""),
    }

    # --- FIFA Ranking ---
    try:
        rankings = api.get_fifa_rankings()
        rank_entry = next(
            (r for r in rankings if r.get("team", {}).get("id") == team_id), None
        )
        if rank_entry:
            rank = rank_entry.get("rank", 100)
        else:
            # Use embedded fallback ranking when API doesn't return this team
            rank = FALLBACK_FIFA_RANKS.get(team_id, 80)
            logger.debug("Using fallback FIFA rank %d for %s", rank, team_name)

        profile["fifa_rank"] = rank
        # Invert: rank 1 → 100, rank 103 → ~2 (actual range of qualified teams)
        profile["fifa_ranking_score"] = max(0.0, (105 - rank) / 104 * 100)
    except Exception as e:
        logger.warning("FIFA ranking fetch failed for %s: %s", team_name, e)
        fallback_rank = FALLBACK_FIFA_RANKS.get(team_id, 80)
        profile["fifa_rank"]          = fallback_rank
        profile["fifa_ranking_score"] = max(0.0, (105 - fallback_rank) / 104 * 100)

    # --- Recent Form (team-perspective-aware) ---
    try:
        fixtures = api.get_team_recent_fixtures(team_id, last=10)
        form_score, gd_score = _compute_form_score(fixtures, team_id)
        profile["recent_form_score"] = form_score
        profile["goal_diff_score"]   = gd_score
    except Exception as e:
        logger.warning("Form fetch failed for %s: %s", team_name, e)
        profile["recent_form_score"] = 50.0
        profile["goal_diff_score"]   = 50.0

    # --- World Cup History ---
    try:
        wc_fixtures = api.get_team_wc_history(team_id)
        if wc_fixtures:
            api_hist, api_exp = _compute_wc_history_score(wc_fixtures)
            # Take max of API value and embedded fallback: protects against
            # partial API coverage (e.g., only 1 of 5 tournaments returned).
            hist_score = max(api_hist, FALLBACK_WC_HISTORY.get(team_id, 10.0))
            exp_score  = max(api_exp,  FALLBACK_TOURNAMENT_EXP.get(team_id, 20.0))
        else:
            hist_score = FALLBACK_WC_HISTORY.get(team_id, 10.0)
            exp_score  = FALLBACK_TOURNAMENT_EXP.get(team_id, 20.0)
        profile["wc_history_score"]     = hist_score
        profile["tournament_exp_score"] = exp_score
    except Exception as e:
        logger.warning("WC history fetch failed for %s: %s", team_name, e)
        profile["wc_history_score"]     = FALLBACK_WC_HISTORY.get(team_id, 10.0)
        profile["tournament_exp_score"] = FALLBACK_TOURNAMENT_EXP.get(team_id, 20.0)

    # --- Squad data (shared between squad_strength and player_performance) ---
    try:
        squad = api.get_squad(team_id)
    except Exception as e:
        logger.warning("Squad fetch failed for %s: %s", team_name, e)
        squad = []

    # Squad depth — use API data when available, else use embedded fallback
    if squad:
        profile["squad_strength_score"] = _compute_squad_strength(squad)
    else:
        profile["squad_strength_score"] = FALLBACK_SQUAD_DEPTH.get(team_id, 65.0)

    # Player performance (primary quality differentiator)
    profile["player_performance_score"] = _compute_player_performance_score(team_id, squad)

    return profile


def build_all_profiles() -> list[dict]:
    """Build metric profiles for all 48 qualified teams."""
    profiles = []
    for team in QUALIFIED_TEAMS:
        try:
            profiles.append(build_team_profile(team))
        except Exception as e:
            logger.error("Failed to build profile for %s: %s", team["name"], e)
    return profiles
