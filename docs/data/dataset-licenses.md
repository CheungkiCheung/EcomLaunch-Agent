# OpenSKU Dataset License And Usage Notes

Date: 2026-06-27

Status: Phase 1 source of truth

This document is an engineering usage boundary, not legal advice. For portfolio and research use, OpenSKU should cite each dataset, preserve license references, and avoid redistributing large raw datasets unless the source license and platform terms allow it.

## License Table

| Dataset | Source | License / Usage Note | OpenSKU Handling |
|---|---|---|---|
| Olist Brazilian E-Commerce Public Dataset | `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`; `https://github.com/olist/work-at-olist-data` | Kaggle metadata reports `CC BY-NC-SA 4.0`. The Olist GitHub work-at-olist repository has an MIT license. Treat the dataset conservatively as attribution-required and non-commercial/share-alike unless the exact distribution being used is clarified. | Use only small samples in this repo. Cite Olist and Kaggle/GitHub source. Do not market this as commercial-ready merchant data. |
| RetailRocket Ecommerce Dataset | `https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset` | Kaggle metadata reports `CC BY-NC-SA 4.0`; download requires Kaggle subscription/API flow. | Map as a first-class future behavior fixture. Do not commit full raw files. Require a separate ingestion log after Kaggle setup. |
| Amazon Reviews 2023 | `https://amazon-reviews-2023.github.io/`; `https://github.com/hyp1231/AmazonReviews2023`; UCSD public raw URLs | The processing/code repository is MIT licensed. The dataset website provides public download links and citation guidance; a separate dataset license was not found during Phase 1. Treat as a research benchmark requiring citation and careful redistribution limits. | Store only tiny sampled rows and generated schemas. Do not redistribute full review/meta files. Do not reuse product images as UI/media assets without separate permission. |
| Amazon ESCI Shopping Queries | `https://github.com/amazon-science/esci-data` | Apache-2.0 license in repository. README asks users to cite the Shopping Queries Dataset paper. | Safe as an eval fixture subject to Apache notice/citation. Add Parquet ingestion before using in cases. |
| Wayfair WANDS | `https://github.com/wayfair/WANDS` | MIT license. README requests citation of the WANDS ECIR 2022 paper. | Use as a product-search benchmark fixture. Preserve license and citation. |
| MAVE | `https://github.com/google-research-datasets/mave` | `CC BY-NC 4.0` license. Full version requires Amazon Review Data 2018 metadata access. | Non-commercial/research only. Use for portfolio evaluation and claim validation, not commercial training or redistribution. |
| Taobao User Behavior | `https://tianchi.aliyun.com/dataset/649?lang=en-us` | Tianchi page is accessible and describes the dataset; download and exact terms require Tianchi account/terms flow. | Do not ingest or redistribute until terms are accepted and recorded in a separate log. |
| TAOBAO-MM | `https://taobao-mm.github.io/`; `https://huggingface.co/datasets/TaoBao-MM/Taobao-MM` | Official site says the dataset is free to download for research purposes under Apache License 2.0. | Treat as a large optional benchmark. Do not commit raw 139 GB dataset. Use generated subsets only after a real download/sample log. |
| ShoppingMMLU / ChineseEcomQA / ShoppingComp / ShoppingBench / ECom-Bench | To be verified in Phase 2 | Candidate external evaluation references; license and source are not yet verified in this repo. | Do not use as accepted fixtures until source, license, fields, and scoring rules are verified. |

## Repository Policy

OpenSKU may commit:

- small sampled rows used as reproducibility evidence.
- generated schema summaries.
- source URL and license metadata.
- benchmark cases derived from public rows, when the case keeps attribution and does not expose more than needed.

OpenSKU should not commit:

- full raw datasets from Kaggle, Tianchi, Hugging Face, UCSD, or Git LFS.
- product images from Amazon or other marketplaces as UI assets.
- records that attempt to de-anonymize users, sellers, visitors, or items.
- commercialized copies of datasets with non-commercial restrictions.
- private merchant data unless the user intentionally uploads it and the docs label it as user-provided.

## Citation Notes

At minimum, future README/eval docs should cite:

- Olist Brazilian E-Commerce Public Dataset by Olist.
- RetailRocket recommender system dataset by Retail Rocket / Kaggle publisher.
- Amazon Reviews 2023 / BLaIR paper by Hou et al.
- Amazon ESCI Shopping Queries Dataset paper by Reddy et al.
- WANDS ECIR 2022 paper by Chen et al.
- MAVE WSDM 2022 paper.
- TAOBAO-MM / MUSE paper when used.

