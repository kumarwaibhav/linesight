# Dataset card: MVTec AD / bottle

**Project owner:** Kumar Waibhav Akshat · kwa.waibhav@gmail.com

## Purpose and source

LineSight uses the bottle category of **MVTec AD**, an industrial visual anomaly benchmark. MVTec provides normal training images and normal/defective test images with anomaly masks. This project uses the images for normal-only learning and image-level evaluation.

Primary source: [MVTec AD dataset page](https://www.mvtec.com/research-teaching/datasets/mvtec-ad). Paper: Paul Bergmann, Michael Fauser, David Sattlegger, and Carsten Steger, *MVTec AD — A Comprehensive Real-World Dataset for Unsupervised Anomaly Detection*, CVPR 2019. The acquisition script and generated provenance record document the exact retrieval source, revision, and hashes used here. A mirror does not change the original dataset's ownership or license.

## Acquired snapshot

The prepared run used the public [`XavierZXY/MvT-tar`](https://huggingface.co/datasets/XavierZXY/MvT-tar) mirror, pinned to revision `dc1c313de9de1be8e41fe6818dc43caac8601efa`. The `bottle.tar.xz` archive is 155,880,244 bytes with SHA-256:

```text
726512129cb3b1f47d4f6cd7c7fc9170db7fc209132249c788fec06029cb5dc3
```

The download is checksum-verified before extraction. The run verified 292 images, 63 masks, expected 900 × 900 image dimensions, and zero duplicate image byte hashes. The snapshot was not independently compared byte-for-byte with an official download. Details live in [`data/provenance.json`](../data/provenance.json); mask hashes are in [`data/mask_checksums.json`](../data/mask_checksums.json).

Use `python scripts/download_data.py --source /path/to/bottle` to prepare an existing dataset directory, or `--verify-only` to verify an acquired copy and regenerate the manifest.

## Task and scope

The task is to flag an image for review when its visual appearance departs from normal bottles under a controlled view. The target is binary image-level anomaly detection. The defect names are evaluation groups, not classes the forest learns to classify.

| Label | Meaning |
| --- | --- |
| `0` | Normal / `good` |
| `1` | Anomalous bottle |

The anomalous test groups are `broken_large` (20), `broken_small` (22), and `contamination` (21). Pixel masks record defect regions, but LineSight does not train a segmentation model or claim pixel-level detection quality.

## Partitions

| Partition | Normal | Anomalous | Role |
| --- | ---: | ---: | --- |
| Fit | 125 | 0 | Learn visual reference and forest |
| Tune | 42 | 0 | Derive synthetic proxies and select a configuration |
| Calibration | 42 | 0 | Determine decision threshold after selection |
| Official test | 20 | 63 | Final evaluation after freezing |
| Total source images | 229 | 63 | 292 images |

The official training set has 209 normal images. Its fit/tune/calibration allocation is deterministic with seed 42. The official test boundary is preserved. Synthetic tune variants are generated at runtime from tune images and are excluded from the count of real source images.

## Preparation and traceability

The downloader writes `data/manifest.csv` with these fields:

| Field | Meaning |
| --- | --- |
| `path` | Image path relative to the repository root |
| `split` | `fit`, `tune`, `calibration`, or `test` |
| `label` | Binary image-level label |
| `defect_type` | `good` or original defect group |
| `sha256` | Source image byte hash |
| `mask_path` | Relative mask path where supplied |

Image decoding, label consistency, counts, checksums, and split disjointness are checked by the data preparation/verification workflow. Model input normalization transposes EXIF orientation, converts RGB, and resizes to a fixed 192 × 192 view with bilinear interpolation. The original data is retained without overwriting it.

Hashes make a local snapshot auditable. A hash obtained from the same mirror as the data is not independent proof of original-source authenticity; source provenance and licensing remain important.

## Leakage policy

- No anomalous official test image participates in reference fitting, forest fitting, candidate selection, or threshold selection.
- Synthetic variants inherit their tune source role; no normal source image crosses fit, tune, calibration, or test roles.
- Normalization statistics come from fit images, rather than the full dataset or each inference batch.
- The threshold uses normal calibration scores only.
- The configuration and threshold are frozen before evaluation. Robustness checks after evaluation measure the frozen model and do not change it.

## Data limitations

The images represent one product category and a controlled benchmark acquisition setting. Images do not establish coverage of changing cameras, conveyors, suppliers, production shifts, rare defect prevalence, or unseen bottle designs. Test anomalies are much more common than a typical operating line might have; benchmark precision therefore should not be interpreted as expected deployment precision.

Only 20 test normals support the observed test false-positive rate. One additional false positive changes it by five percentage points. Independent batch-level field validation is needed before operational decisions.

## License and attribution

MVTec AD is released under [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-nc-sa/4.0/). MVTec explicitly excludes commercial dataset use. Give credit, retain the license, and identify modifications when sharing covered material. The MIT license for LineSight software does not apply to the original dataset.

Raw images are excluded from the source-control package. Data-derived example panels, visualizations, and supplied model artifacts are separately identified in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Obtain appropriate permissions or use appropriately licensed replacement data for a commercial installation.
