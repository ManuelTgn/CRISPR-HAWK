""" """

from .crisprhawk_error import CrisprHawkGuidesReportError
from .exception_handlers import exception_handler
from .pam import PAM
from .guide import Guide
from .region_constructor import PADDING
from .region import Region
from .utils import (
    print_verbosity,
    VERBOSITYLVL,
    GUIDESREPORTPREFIX,
    IUPACTABLE,
    IUPAC,
    STRAND,
)

from typing import List, Dict, Set, Any
from time import time

import pandas as pd

import os


REPORTCOLS = [
    "chr",
    "start",
    "stop",
    "sgRNA_sequence",
    "pam",
    "pam_class",
    "strand",
    "score_azimuth",
    "score_rs3",
    "score_cfdon",
    "origin",
    "samples",
    "variant_id",
    "target",
    "haplotype_id",
    "functional_annotation",
    "gene_annotation",
]


def compute_pam_class(pam: PAM) -> str:
    # retrieve a string representing the input pam class
    # e.g. NGG -> [ACGT]GG
    return "".join([nt if nt in IUPAC[:4] else f"[{IUPACTABLE[nt]}]" for nt in pam.pam])


def compute_guide_origin(samples: str) -> str:
    # compute whether the guide came from reference or alternative genomes
    return "ref" if samples == "REF" else "alt"


def compute_strand_orientation(strand: int) -> str:
    # retrieve strand orientation
    return "+" if strand == STRAND[0] else "-"  # retrieve strand orientation


def update_report_fields(
    report: Dict[str, List[Any]], region: Region, guide: Guide, pamclass: str
) -> Dict[str, List[str]]:
    # update report fields
    report[REPORTCOLS[1]].append(guide.start)  # start and stop position
    report[REPORTCOLS[2]].append(guide.stop)
    report[REPORTCOLS[3]].append(guide.guide)  # guide sequence
    report[REPORTCOLS[4]].append(guide.pam)  # pam guide
    report[REPORTCOLS[5]].append(pamclass)  # extended pam class
    # strand orientation
    report[REPORTCOLS[6]].append(compute_strand_orientation(guide.strand))
    report[REPORTCOLS[7]].append(guide.azimuth_score)  # azimuth score
    report[REPORTCOLS[8]].append(guide.rs3_score)  # rs3 score
    report[REPORTCOLS[9]].append(guide.cfdon_score)  # cfdon score
    report[REPORTCOLS[10]].append(compute_guide_origin(guide.samples))  # genome
    report[REPORTCOLS[11]].append(guide.samples)  # samples list
    report[REPORTCOLS[12]].append(guide.variants)  # variant ids
    report[REPORTCOLS[13]].append(str(region.coordinates))  # region
    report[REPORTCOLS[14]].append(guide.hapid)  # haplotype id
    return report

def update_optional_report_fields(report: Dict[str, List[Any]], guide: Guide, funcann: bool, geneann: bool) -> Dict[str, List[str]]:
    # update report optional fields
    if funcann:
        report[REPORTCOLS[15]].append(guide.funcann)
    if geneann:
        report[REPORTCOLS[16]].append(guide.geneann)
    return report


def process_data(region: Region, guides: List[Guide], pam: PAM, funcann: bool, geneann: bool) -> pd.DataFrame:
    report = {cname: [] for cname in REPORTCOLS}  # initialize report dictionary
    pamclass = compute_pam_class(pam)  # compute extended pam class
    for guide in guides:  # iterate over guides and add to report
        report[REPORTCOLS[0]].append(region.contig)  # region contig (chrom)
        # update report with current guide data
        report = update_report_fields(report, region, guide, pamclass)
        report = update_optional_report_fields(report, guide, funcann, geneann)
    report = {c: v for c, v in report.items() if v}  # remove empty columns
    return pd.DataFrame(report)  # build dataframe from report data


def construct_report(
    guides: Dict[Region, List[Guide]], pam: PAM, funcann: bool, geneann: bool
) -> Dict[Region, pd.DataFrame]:
    return {
        region: process_data(region, guides_list, pam, funcann, geneann)
        for region, guides_list in guides.items()
    }


def format_report(report: pd.DataFrame, funcann: bool, geneann: bool) -> pd.DataFrame:
    # reset dataframe index and sort by genomic coordinates
    report = report.reset_index(drop=True)
    report = report.sort_values([REPORTCOLS[7]], ascending=False)
    # force start and stop to int values - they may be treated as float if
    # concatenated with empty dataframe (e.g. no guide found on + or - strand)
    report[REPORTCOLS[1]] = report[REPORTCOLS[1]].astype(int)
    report[REPORTCOLS[2]] = report[REPORTCOLS[2]].astype(int)
    # sort the report columns
    report_cols = REPORTCOLS[:10]
    if funcann:
        report_cols.append(REPORTCOLS[15])
    if geneann:
        report_cols.append(REPORTCOLS[16])
    report_cols += REPORTCOLS[10:15]
    report = report[report_cols]
    return report


def store_report(report: pd.DataFrame, guidesreport: str, funcann: bool, geneann: bool, debug: bool) -> None:
    try:
        report = format_report(report, funcann, geneann)  # format report
        report.to_csv(guidesreport, sep="\t", index=False)  # store report
    except FileNotFoundError as e:
        exception_handler(
            CrisprHawkGuidesReportError,  # type: ignore
            f"Unable to write to {guidesreport}",
            os.EX_OSERR,
            debug,
            e,
        )
    except PermissionError as e:
        exception_handler(
            CrisprHawkGuidesReportError,  # type: ignore
            f"Permission denied to write {guidesreport}",
            os.EX_OSERR,
            debug,
            e,
        )
    except Exception as e:
        exception_handler(
            CrisprHawkGuidesReportError,  # type: ignore
            f"An unexpected error occurred while writing {guidesreport}",
            os.EX_OSERR,
            debug,
            e,
        )


def collapse_samples(samples: pd.Series) -> str:
    return "" if samples.empty else ",".join(sorted(set(",".join(samples).split(","))))


def parse_variant_ids(variant_ids: str) -> Set[str]:
    return set(variant_ids.split(",")) if variant_ids else set()


def check_variant_ids(variant_ids_list: List[str]) -> str:
    variant_sets = [parse_variant_ids(vid) for vid in variant_ids_list]
    unique_variant_ids_sets = {tuple(sorted(vs)) for vs in variant_sets}
    return ",".join(sorted(unique_variant_ids_sets.pop()))


def collapse_haplotype_ids(hapids: pd.Series) -> str:
    return "" if hapids.empty else ",".join(sorted(set(",".join(hapids).split(","))))

def collapse_annotation(anns: pd.Series) -> str:
    return ",".join(set(",".join(anns).split(",")))

def collapsed_fields(funcann: bool, geneann: bool) -> Dict[str, str]:
    # mandatory report fields
    fields = {
        "pam_class": "first",  # Assuming pam_class is the same across entries
        "origin": "first",  # Assuming origin does not change
        "samples": collapse_samples,  # Merge sample lists
        "variant_id": check_variant_ids,  # Ensure identical variant_id
        "target": "first",  # Keep the first target entry
        "haplotype_id": collapse_haplotype_ids,  # Merge haplotype IDs
    }
    # add optional report fields
    if funcann:  # guides functional annotation
        fields["functional_annotation"] = collapse_annotation
    if geneann:
        fields["gene_annotation"] = collapse_annotation
    return fields

def collapse_report_entries(report: pd.DataFrame, funcann: bool, geneann: bool) -> pd.DataFrame:
    # Define the columns to group by
    group_cols = REPORTCOLS[:5] + REPORTCOLS[6:11]
    if funcann:
        group_cols.append(REPORTCOLS[15])
    if geneann:
        group_cols.append(REPORTCOLS[16])
    return report.groupby(group_cols, as_index=False).agg(
        collapsed_fields(funcann, geneann)
    )


def report_guides(
    guides: Dict[Region, List[Guide]],
    guidelen: int,
    pam: PAM,
    funcann: bool,
    geneann: bool,
    outdir: str,
    verbosity: int,
    debug: bool,
) -> None:
    print_verbosity("Constructing reports", verbosity, VERBOSITYLVL[1])
    start = time()  # report construction start time
    reports = construct_report(guides, pam, funcann, geneann)  # construct reports
    for region, report in reports.items():  # store reports in output folder
        region_name = (
            f"{region.contig}_{region.start + PADDING}_{region.stop - PADDING}"
        )
        guidesreport = os.path.join(
            outdir, f"{GUIDESREPORTPREFIX}__{region_name}_{pam}_{guidelen}.tsv"
        )
        report = collapse_report_entries(report, funcann, geneann)
        store_report(report, guidesreport, funcann, geneann, debug)  # write report
    print_verbosity(
        f"Reports constructed in {time() - start:.2f}s", verbosity, VERBOSITYLVL[2]
    )
