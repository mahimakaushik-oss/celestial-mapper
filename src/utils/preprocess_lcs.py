"""Preprocess LC and injected planet files for reducing compute/memory requirements during training.
"""
import os
import argparse

from glob import glob

import astropy.io.fits as pf
from tqdm.autonotebook import trange

import numpy as np
import pandas as pd


def preprocess_flux(root_path, save_path, bin_factor, flux_type="planet"):
    """Bin the planet fluxes into a csv file.
    Params:
    - root_path (str): path to flux txt files
    - save_path (str): path to save csv files
    - bin_factor (int): bin factor for light curves
    - flux_type (str): type of flux to bin (eb or planet)
    """
    os.makedirs(save_path, exist_ok=True)
    if flux_type == "planet":
        planet_files = glob(f"{root_path}/Planets_*.txt")
    elif flux_type == "eb":
        planet_files = glob(f"{root_path}/EBs_*.txt")
    else:
        raise ValueError("flux_type must be 'planet' or 'eb'")
    print(f"Found {len(planet_files)} files")
    with trange(len(planet_files)) as t: 
        for planet_file in planet_files:
            # read the file
            flux = np.genfromtxt(planet_file, delimiter=',')
            
            # bin flux
            N = len(flux)
            n = int(np.floor(N / bin_factor) * bin_factor)
            X = np.zeros((1, n))
            X[0, :] = flux[:n]
            Xb = rebin(X, (1, int(n / bin_factor)))
            flux_binned = Xb[0]

            _, file_name = os.path.split(planet_file)
            file_name += f"_binfac-{bin_factor}.csv"

            # save the file
            file_name = os.path.join(save_path, file_name)
            pd.DataFrame({"flux": flux_binned}).to_csv(file_name, index=False)
            # np.savetxt(file_name, flux, delimiter=",") # csv
            t.update()


def preprocess_lcs(lc_root_path, save_path, sectors, bin_factor):
    """Preprocesses light curves into csv files with names containing the metadata.
    Loads fits files from each sector, takes PDCSAP_FLUX and time, bins flux, and saves to csv files. 
    Metadata in the file name in case this is useful: tic_id, sector, samera, ccd, tess magnitude, effective temperature, radius
    File naming convention: {save_path}/Sector{sector}/tic-{tic_id}_sec-{sector}_cam-{camera}_chi-{ccd}_tessmag-{}_teff-{teff}_srad-{radius}_cdpp05-{cdpp_0_5}_cdpp1-{cdpp_1_0}_cdpp2-{cdpp_2_0}_binfac-{bin_factor}.csv
    Params:
    - lc_root_path (str): path to lc fits files
    - save_path (str): path to save csv files
    - sectors (List(int)): sectors to preprocess
    - bin_factor (int): bin factor for light curves
    """

    for sector in sectors:
        print(f"Preprocessing sector {sector}")
        # make the directory if it doesn't exist
        os.makedirs(os.path.join(save_path, "Sector{}".format(sector)), exist_ok=True)
        # get the list of files in the sector
        fits_files = glob(os.path.join(lc_root_path, f"planethunters/Rel{sector}/Sector{sector}/**/*.fit*"), recursive=True)
        print(f"Found {len(fits_files)} files")
        with trange(len(fits_files)) as t: 
            for i, fits_file in enumerate(fits_files):
                # read the file
                time, flux, file_name = _read_lc(fits_file)
                if time is None:
                    continue
                
                # bin flux
                N = len(time)
                n = int(np.floor(N / bin_factor) * bin_factor)
                X = np.zeros((2, n))
                X[0, :] = time[:n]
                X[1, :] = flux[:n]
                Xb = rebin(X, (2, int(n / bin_factor)))
                time_binned = Xb[0]
                flux_binned = Xb[1]

                file_name += f"_binfac-{bin_factor}.csv"

                # save the file
                file_name = os.path.join(save_path, "Sector{}".format(sector), file_name)
                pd.DataFrame({"time": time_binned, "flux": flux_binned}).to_csv(file_name, index=False)

                t.update()


def rebin(arr, new_shape):
    """Function to bin the data. Uses nanmean to deal with missing values.
    Params:
    - arr (np.array): array to bin
    - new_shape (tuple): shape of the new array
    """
    shape = (
        new_shape[0],
        arr.shape[0] // new_shape[0],
        new_shape[1],
        arr.shape[1] // new_shape[1],
    )
    return np.nanmean(np.nanmean(arr.reshape(shape), axis=(-1)), axis=1)
    # return arr.reshape(shape).mean(-1).mean(1)


def _read_lc(lc_file):
    """Read light curve file (copy from data.py)
    Returns:
    - time (np.array): time array
    - flux (np.array): flux array
    - file_name (str): file name
    """
    # open the file in context manager - catching corrupt files
    try:
        with pf.open(lc_file) as hdul:
            d = hdul[1].data
            hdr = hdul[1].header
            time = np.array(d["TIME"])  # currently not using time
            flux = np.array(d["PDCSAP_FLUX"])  # the processed flux
            qual = d['QUALITY']

            # l = np.isfinite(time) * np.isfinite(flux) * (qual == 0)
            low_qual = (qual > 0)  # bad quality
            
            # remove bad data
            flux[low_qual] = np.nan

            t0 = time[0]  # make the time start at 0 (so that the timeline always runs from 0 to 27.8 days)
            time -= t0

            tic = int(hdul[0].header["TICID"])
            sec = int(hdul[0].header["SECTOR"])
            cam = int(hdul[0].header["CAMERA"])
            chi = int(hdul[0].header["CCD"])
            tessmag = hdul[0].header["TESSMAG"]
            teff = hdul[0].header["TEFF"]
            srad = hdul[0].header["RADIUS"]
            cdpp_0_5 =hdr["CDPP0_5"]
            cdpp_1_0 = hdr["CDPP1_0"]
            cdpp_2_0 = hdr["CDPP2_0"]

            file_name = f"tic-{tic}_sec-{sec}_cam-{cam}_chi-{chi}_tessmag-{tessmag}_teff-{teff}_srad-{srad}_cdpp05-{cdpp_0_5}_cdpp1-{cdpp_1_0}_cdpp2-{cdpp_2_0}"
    except:
        print("Error in fits file: ", lc_file)
        return None, None, None

    return time, flux, file_name


if __name__ == "__main__":
    # manually change which sectors here
    SECTORS = [39,40,41,42,43]
    # SECTORS = list(range(25, 38))

    # parse args
    ap = argparse.ArgumentParser(description="test dataloader")
    ap.add_argument("--lc-root-path", type=str, default="./data/TESS")
    ap.add_argument("--planets-root-path", type=str, default=".data/TESS/ETE-6/injected/Planets")
    ap.add_argument("--eb-root-path", type=str, default="./data/eb_raw/EBs")
    ap.add_argument("--labels-root-path", type=str, default="./data/pht_labels")
    ap.add_argument("--save-path", type=str, default="./data/lc_csvs_cdpp")
    ap.add_argument("--planets-save-path", type=str, default="./data/planet_csvs")
    ap.add_argument("--eb-save-path", type=str, default="./data/eb_csvs")
    ap.add_argument("--bin-factor", type=int, default=7)
    ap.add_argument("--skip-planets", action="store_true")
    ap.add_argument("--skip-ebs", action="store_true")
    ap.add_argument("--skip-lcs", action="store_true")
    args = ap.parse_args()
    print(args)

    if not args.skip_planets:
        print("\nPreprocessing planets")
        preprocess_flux(args.planets_root_path, args.planets_save_path, args.bin_factor, flux_type="planet")
    if not args.skip_ebs:
        print("\nPreprocessing EBs")
        preprocess_flux(args.eb_root_path, args.eb_save_path, args.bin_factor, flux_type="eb")
    if not args.skip_lcs:
        print("\nPreprocessing light curves")
        preprocess_lcs(args.lc_root_path, args.save_path, SECTORS, args.bin_factor)


