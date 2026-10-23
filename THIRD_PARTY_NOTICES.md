# Third-party notices

The original LineSight source code is MIT licensed, copyright 2026 Kumar Waibhav Akshat.

## MVTec AD bottle

Dataset copyright belongs to MVTec Software GmbH and the original authors.
Source: https://www.mvtec.com/research-teaching/datasets/mvtec-ad
Paper: https://openaccess.thecvf.com/content_CVPR_2019/html/Bergmann_MVTec_AD_--_A_Comprehensive_Real-World_Dataset_for_Unsupervised_Anomaly_CVPR_2019_paper.html
License: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International**
https://creativecommons.org/licenses/by-nc-sa/4.0/

The dataset is used for educational, noncommercial inspection benchmarking.
The raw dataset is excluded from the Git source distribution. An offline data
bundle, when supplied, retains its original license and attribution.
The pretrained artifact, reference statistics and dataset-derived images/figures
are provided for noncommercial use under CC BY-NC-SA 4.0; the code MIT license
does not remove dataset restrictions. Obtain separately licensed production
images and retrain for a commercial deployment. No commercial permission or
endorsement from MVTec is implied.

Original data are unmodified in data/raw; preprocessing resizes and normalizes
inputs; synthetic tune defects are generated from tune normals only.

Bergmann, P., Fauser, M., Sattlegger, D., and Steger, C. (2019). MVTec AD - A
Comprehensive Real-World Dataset for Unsupervised Anomaly Detection. CVPR.

## Software dependencies

NumPy, SciPy, scikit-learn, Pillow, Matplotlib, joblib, FastAPI, uvicorn and
python-multipart retain their respective upstream licenses. Dependencies are
installed separately; consult their distributions for complete notices.
