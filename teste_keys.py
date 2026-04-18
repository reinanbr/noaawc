"""
test_variables.py
-----------------
Testa cada key do dicionário VARIABLES fazendo uma requisição HEAD ao
NOMADS grib-filter com a data/ciclo mais recente disponível.

Execução:
    python test_variables.py

Saída:
    ✅ t2m     → 200
    ❌ cwat    → 404  (level errado / var não encontrada)
    ...

Ao final imprime um resumo e sugestões de correção.
"""

import datetime
import sys
from typing import Any
from urllib3.util.retry import Retry
import requests
from requests.adapters import HTTPAdapter

# ──────────────────────────────────────────────────────────────────────────────
# Cópia do dicionário VARIABLES (exatamente como no seu código-fonte)
# ──────────────────────────────────────────────────────────────────────────────
VARIABLES: dict[str, dict[str, Any]] = {
    "t2m":   {"short":"t2m","long_name":"2 metre temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_TMP","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "d2m":   {"short":"d2m","long_name":"2 metre dewpoint temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_DPT","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "r2":    {"short":"r2","long_name":"2 metre relative humidity","units":"%","tlev":"heightAboveGround","levels":[2],"grib_var":"var_RH","grib_lev":"lev_2_m_above_ground","converter":None},
    "sh2":   {"short":"sh2","long_name":"2 metre specific humidity","units":"kg kg**-1","tlev":"heightAboveGround","levels":[2],"grib_var":"var_SPFH","grib_lev":"lev_2_m_above_ground","converter":None},
    "aptmp": {"short":"aptmp","long_name":"Apparent temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_APTMP","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "u10":   {"short":"u10","long_name":"10 metre U wind component","units":"m s**-1","tlev":"heightAboveGround","levels":[10],"grib_var":"var_UGRD","grib_lev":"lev_10_m_above_ground","converter":None},
    "v10":   {"short":"v10","long_name":"10 metre V wind component","units":"m s**-1","tlev":"heightAboveGround","levels":[10],"grib_var":"var_VGRD","grib_lev":"lev_10_m_above_ground","converter":None},
    "gust":  {"short":"gust","long_name":"Wind speed (gust)","units":"m s**-1","tlev":"surface","levels":None,"grib_var":"var_GUST","grib_lev":"lev_surface","converter":None},
    "prmsl": {"short":"prmsl","long_name":"Pressure reduced to MSL","units":"hPa","tlev":"meanSea","levels":None,"grib_var":"var_PRMSL","grib_lev":"lev_mean_sea_level","converter":lambda x:x/100},
    "mslet": {"short":"mslet","long_name":"MSLP (Eta model reduction)","units":"hPa","tlev":"meanSea","levels":None,"grib_var":"var_MSLET","grib_lev":"lev_mean_sea_level","converter":lambda x:x/100},
    "sp":    {"short":"sp","long_name":"Surface pressure","units":"hPa","tlev":"surface","levels":None,"grib_var":"var_PRES","grib_lev":"lev_surface","converter":lambda x:x/100},
    "orog":  {"short":"orog","long_name":"Orography","units":"m","tlev":"surface","levels":None,"grib_var":"var_HGT","grib_lev":"lev_surface","converter":None},
    "lsm":   {"short":"lsm","long_name":"Land-sea mask","units":"0 - 1","tlev":"surface","levels":None,"grib_var":"var_LAND","grib_lev":"lev_surface","converter":None},
    "vis":   {"short":"vis","long_name":"Visibility","units":"m","tlev":"surface","levels":None,"grib_var":"var_VIS","grib_lev":"lev_surface","converter":None},
    "prate": {"short":"prate","long_name":"Precipitation rate","units":"kg m**-2 s**-1","tlev":"surface","levels":None,"grib_var":"var_PRATE","grib_lev":"lev_surface","converter":None},
    "cpofp": {"short":"cpofp","long_name":"Percent frozen precipitation","units":"%","tlev":"surface","levels":None,"grib_var":"var_CPOFP","grib_lev":"lev_surface","converter":None},
    "crain": {"short":"crain","long_name":"Categorical rain","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CRAIN","grib_lev":"lev_surface","converter":None},
    "csnow": {"short":"csnow","long_name":"Categorical snow","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CSNOW","grib_lev":"lev_surface","converter":None},
    "cfrzr": {"short":"cfrzr","long_name":"Categorical freezing rain","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CFRZR","grib_lev":"lev_surface","converter":None},
    "cicep": {"short":"cicep","long_name":"Categorical ice pellets","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CICEP","grib_lev":"lev_surface","converter":None},
    "sde":   {"short":"sde","long_name":"Snow depth","units":"m","tlev":"surface","levels":None,"grib_var":"var_SNOD","grib_lev":"lev_surface","converter":None},
    "sdwe":  {"short":"sdwe","long_name":"Water equivalent of accumulated snow depth","units":"kg m**-2","tlev":"surface","levels":None,"grib_var":"var_WEASD","grib_lev":"lev_surface","converter":None},
    "pwat":  {"short":"pwat","long_name":"Precipitable water","units":"kg m**-2","tlev":"atmosphereSingleLayer","levels":None,"grib_var":"var_PWAT","grib_lev":"lev_entire_atmosphere_(considered_as_a_single_layer)","converter":None},
    "cwat":  {"short":"cwat","long_name":"Cloud water","units":"kg m**-2","tlev":"atmosphereSingleLayer","levels":None,"grib_var":"var_CWAT","grib_lev":"lev_entire_atmosphere_(considered_as_a_single_layer)","converter":None},
    "tcc":   {"short":"tcc","long_name":"Total cloud cover","units":"%","tlev":"atmosphere","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_entire_atmosphere","converter":None},
    "lcc":   {"short":"lcc","long_name":"Low cloud cover","units":"%","tlev":"lowCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_low_cloud_layer","converter":None},
    "mcc":   {"short":"mcc","long_name":"Medium cloud cover","units":"%","tlev":"middleCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_middle_cloud_layer","converter":None},
    "hcc":   {"short":"hcc","long_name":"High cloud cover","units":"%","tlev":"highCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_high_cloud_layer","converter":None},
    "cape":  {"short":"cape","long_name":"Convective available potential energy","units":"J kg**-1","tlev":"surface","levels":None,"grib_var":"var_CAPE","grib_lev":"lev_surface","converter":None,"multilevel":True},
    "cin":   {"short":"cin","long_name":"Convective inhibition","units":"J kg**-1","tlev":"surface","levels":None,"grib_var":"var_CIN","grib_lev":"lev_surface","converter":None,"multilevel":True},
    "lftx":  {"short":"lftx","long_name":"Surface lifted index","units":"K","tlev":"surface","levels":None,"grib_var":"var_LFTX","grib_lev":"lev_surface","converter":None},
    "lftx4": {"short":"lftx4","long_name":"Best (4-layer) lifted index","units":"K","tlev":"surface","levels":None,"grib_var":"var_4LFTX","grib_lev":"lev_surface","converter":None},
    "hlcy":  {"short":"hlcy","long_name":"Storm relative helicity","units":"m**2 s**-2","tlev":"heightAboveGroundLayer","levels":None,"grib_var":"var_HLCY","grib_lev":"lev_height_above_ground_layer","converter":None},
    "t":     {"short":"t","long_name":"Temperature","units":"C","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_TMP","grib_lev":"lev_500_mb","converter":lambda x:x-273.15,"multilevel":True},
    "r":     {"short":"r","long_name":"Relative humidity","units":"%","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_RH","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "q":     {"short":"q","long_name":"Specific humidity","units":"kg kg**-1","tlev":"isobaricInhPa","levels":[1000],"grib_var":"var_SPFH","grib_lev":"lev_1000_mb","converter":None,"multilevel":True},
    "gh":    {"short":"gh","long_name":"Geopotential height","units":"gpm","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_HGT","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "u":     {"short":"u","long_name":"U component of wind","units":"m s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_UGRD","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "v":     {"short":"v","long_name":"V component of wind","units":"m s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_VGRD","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "w":     {"short":"w","long_name":"Vertical velocity","units":"Pa s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_VVEL","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "absv":  {"short":"absv","long_name":"Absolute vorticity","units":"s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_ABSV","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "st":    {"short":"st","long_name":"Soil temperature","units":"C","tlev":"depthBelowLandLayer","levels":[0],"grib_var":"var_TSOIL","grib_lev":"lev_0-10_cm_below_ground","converter":lambda x:x-273.15,"multilevel":True},
    "soilw": {"short":"soilw","long_name":"Volumetric soil moisture content","units":"Proportion","tlev":"depthBelowLandLayer","levels":[0],"grib_var":"var_SOILW","grib_lev":"lev_0-10_cm_below_ground","converter":None,"multilevel":True},
    "refc":  {"short":"refc","long_name":"Maximum/Composite radar reflectivity","units":"dB","tlev":"atmosphere","levels":None,"grib_var":"var_REFC","grib_lev":"lev_entire_atmosphere","converter":None},
    "siconc":{"short":"siconc","long_name":"Sea ice area fraction","units":"0 - 1","tlev":"surface","levels":None,"grib_var":"var_ICEC","grib_lev":"lev_surface","converter":None},
    "veg":   {"short":"veg","long_name":"Vegetation","units":"%","tlev":"surface","levels":None,"grib_var":"var_VEG","grib_lev":"lev_surface","converter":None},
    "tozne": {"short":"tozne","long_name":"Total ozone","units":"DU","tlev":"atmosphere","levels":None,"grib_var":"var_TOZNE","grib_lev":"lev_entire_atmosphere","converter":None},
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
_FILTER_BASE = (
    "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25_1hr.pl"
    "?dir=/gfs.{date}/{cycle}/atmos"
    "&file=gfs.t{cycle}z.pgrb2.0p25.f{hour:03d}"
    "{var_params}"
    "{region_params}"
)

_RETRY = Retry(
    total=2,
    backoff_factor=0.5,
    status_forcelist={429, 500, 502, 503, 504},
    allowed_methods={"GET", "HEAD"},
    raise_on_status=False,
)
_HEADERS = {"User-Agent": "GFS-test/1.0"}


def make_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def latest_run() -> tuple[str, str]:
    """Retorna (YYYYMMDD, cycle) do ciclo GFS mais recente disponível."""
    now = datetime.datetime.utcnow()
    # ciclos disponíveis: 00, 06, 12, 18 – com ~4 h de latência
    for back_h in range(0, 24, 6):
        t = now - datetime.timedelta(hours=back_h + 4)
        cycle = f"{(t.hour // 6) * 6:02d}"
        date = t.strftime("%Y%m%d")
        return date, cycle
    return now.strftime("%Y%m%d"), "00"


def build_url(var_cfg: dict, date: str, cycle: str, hour: int = 6) -> str:
    grib_var  = var_cfg["grib_var"]
    grib_lev  = var_cfg["grib_lev"]
    var_params = f"&{grib_var}=on&{grib_lev}=on"
    # pequena região só para HEAD/GET rápido (1°×1° em torno de 0N 0E)
    region_params = "&subregion=&leftlon=-1&rightlon=1&toplat=1&bottomlat=-1"
    return _FILTER_BASE.format(
        date=date, cycle=cycle, hour=hour,
        var_params=var_params, region_params=region_params,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def run_tests():
    date, cycle = latest_run()
    print(f"\n{'='*60}")
    print(f"  GFS run: {date}  cycle: {cycle}z")
    print(f"{'='*60}\n")

    session = make_session()
    passed, failed = [], []

    for key, cfg in VARIABLES.items():
        url = build_url(cfg, date, cycle)
        try:
            resp = session.get(url, headers=_HEADERS, timeout=15, stream=True)
            # lê apenas os primeiros bytes para verificar se há conteúdo GRIB
            chunk = next(resp.iter_content(128), b"")
            resp.close()

            # NOMADS retorna 200 mesmo em erro — verifica o magic number GRIB
            is_grib = chunk[:4] == b"GRIB"
            status   = resp.status_code

            if is_grib:
                print(f"  {GREEN}✅ {key:<8}{RESET}  HTTP {status}  GRIB magic ✓")
                passed.append(key)
            else:
                snippet = chunk[:120].decode("utf-8", errors="replace").strip()
                print(f"  {RED}❌ {key:<8}{RESET}  HTTP {status}  body: {snippet[:80]!r}")
                failed.append((key, cfg, snippet))

        except Exception as exc:
            print(f"  {YELLOW}⚠️  {key:<8}{RESET}  EXCEPTION: {exc}")
            failed.append((key, cfg, str(exc)))

    # ── Resumo ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Passed : {len(passed)}/{len(VARIABLES)}")
    print(f"  Failed : {len(failed)}")
    print(f"{'='*60}\n")

    if failed:
        print(f"{YELLOW}Keys com problema:{RESET}")
        for item in failed:
            key, cfg, info = item
            print(f"\n  key      : {key}")
            print(f"  grib_var : {cfg['grib_var']}")
            print(f"  grib_lev : {cfg['grib_lev']}")
            print(f"  info     : {info[:120]}")

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    sys.exit(0 if not failed else 1)
